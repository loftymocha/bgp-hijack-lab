# BGP Hijack + RPKI Lab

A four-AS internet in a box. You will originate a prefix legitimately, steal it from
another AS, watch the theft propagate, then stop it with RPKI origin validation.

This is the same failure mode behind the real-world incidents — Pakistan Telecom/YouTube
(2008), the Rostelecom leak (2020), the MyEtherWallet BGP+DNS theft (2018). The mechanism
you build here is exactly the mechanism that broke those.

**Time:** ~2 hours for Phases 1–4. Phase 5 is a separate evening.

---

## Topology

```
                      AS65001  transit  10.99.0.1
                     /         |          \
                    /          |           \
   AS65002  isp  10.99.0.2   AS65003     AS65004  rogue  10.99.0.4
   originates                customer    hijacks the same prefix
   203.0.113.0/24            10.99.0.3
                             (you watch from here)

                     stayrtr  10.99.0.10   RPKI cache, RTR on :3323
```

`transit` is deliberately a bad actor by omission: it accepts anything its peers announce
and passes it on. That is not a strawman — it is how a large share of the internet still
works, and it is why RPKI exists.

`203.0.113.0/24` and `198.51.100.0/24` are RFC 5737 documentation ranges. They are not
routable on the real internet, which is why this is safe to run.

---

## Setup

Copy the whole `bgp-lab` directory to the Unraid box (anywhere under `/mnt/user/`
that isn't a share you care about — `/mnt/user/appdata/bgp-lab` is fine), then:

```bash
docker compose up -d
```

Confirm all five are running:

```bash
docker compose ps
```

**Before going further, verify the RPKI module actually loaded.** This is the one thing
most likely to bite you, because not every FRR build ships it:

```bash
docker exec bgp-customer ls /usr/lib/frr/modules/ | grep rpki
```

You want to see `bgpd_rpki.so`. If it's missing, see Troubleshooting at the bottom —
Phases 1, 2 and 4 still work fine without it, you just can't do Phase 3 as written.

Get a router CLI (this is `vtysh`, and it is deliberately near-identical to IOS —
`show`, `configure terminal`, `?` completion all behave the way you already expect):

```bash
docker exec -it bgp-customer vtysh
```

---

## Phase 1 — Normal internet

Log into `customer` and confirm the session to transit came up:

```
show ip bgp summary
```

`State/PfxRcd` should show a number, not `Active` or `Idle`. If it says `Active`, BGP is
trying and failing — check Troubleshooting.

Now look at what you learned:

```
show ip bgp
```

You should see `203.0.113.0/24` with AS path `65001 65002`. Read that right to left:
originated by 65002, passed through 65001, arrived at you.

Look at the detail for the prefix:

```
show ip bgp 203.0.113.0/24
```

Note the origin AS, the next-hop, and — importantly — that there is exactly **one** path.

Now check the RPKI cache is feeding you data:

```
show rpki cache-connection
show rpki prefix-table
```

You should see the two ROAs from `vrps.json`: `203.0.113.0/24` maxlen 24 origin AS65002.
That is a *Validated ROA Payload* — a cryptographic statement that only AS65002 is
allowed to originate that prefix. Right now you are receiving that statement and ignoring it.

Check what FRR thinks of the route you have:

```
show bgp ipv4 unicast rpki valid
```

`203.0.113.0/24` should be listed. Good — origin matches the ROA.

**Before moving on, write down what you expect to happen in Phase 2.** Actually write it.
Predicting and being wrong is where the learning is.

---

## Phase 2 — The hijack

Open a second terminal into the rogue AS:

```bash
docker exec -it bgp-rogue vtysh
```

Announce someone else's prefix:

```
configure terminal
router bgp 65004
 address-family ipv4 unicast
  network 203.0.113.0/24
 exit-address-family
exit
exit
```

Now go back to `customer` and look again:

```
show ip bgp 203.0.113.0/24
```

You now have **two** paths: `65001 65002` (real) and `65001 65004` (stolen). Both AS paths
are the same length, so the tiebreak falls to lower router-id / oldest path — the legit
route probably still wins. That is luck, not security.

So make it not luck. Back on `rogue`, announce **more specifics**:

```
configure terminal
router bgp 65004
 address-family ipv4 unicast
  network 203.0.113.0/25
  network 203.0.113.128/25
 exit-address-family
end
```

Back on `customer`:

```
show ip bgp
show ip route 203.0.113.50
```

**This is the whole lesson.** Longest-prefix-match is not a policy decision — it is how
forwarding works, at every router, unconditionally. Two /25s beat a /24 every time,
regardless of who is legitimate, regardless of AS path length, regardless of anything.
The rogue AS now receives all traffic for that space and there is no BGP mechanism that
noticed. You cannot outrun this with better path selection. You have to reject the
announcement at the door.

Confirm the routes are formally invalid, even though you're using them:

```
show bgp ipv4 unicast rpki invalid
```

There they are. FRR knew the whole time. Nobody told it to care.

---

## Phase 3 — The fix (RPKI origin validation)

On `customer`, apply the route-map that's been sitting staged in the config:

```
configure terminal
router bgp 65003
 address-family ipv4 unicast
  neighbor 10.99.0.1 route-map RPKI-FILTER in
 exit-address-family
end
clear bgp ipv4 unicast * soft in
```

Wait a few seconds, then:

```
show ip bgp
show ip route 203.0.113.50
```

The /25s are gone. The legitimate /24 from AS65002 is back in the forwarding table.

Prove to yourself the filter is doing it rather than the rogue giving up:

```
show ip bgp neighbors 10.99.0.1 received-routes
show ip bgp neighbors 10.99.0.1 routes
```

The first shows what arrived on the wire. The second shows what survived policy. The
difference between those two commands is the entire concept of inbound filtering, and it
is worth internalizing — a lot of "the route is missing" tickets are resolved by knowing
which of those two to run.

### Things to try before moving on

- On `rogue`, try announcing `198.51.100.0/24`. Also covered by a ROA — also rejected.
- On `rogue`, try announcing `192.0.2.0/24`. **No ROA covers it**, so validation returns
  `not-found`, not `invalid`, and your route-map permits it. This is the real limitation
  of RPKI: it only protects prefixes whose holders bothered to publish a ROA. Global ROA
  coverage is well short of complete. Understanding *why not-found must be permitted* —
  because dropping it would break most of the internet — is the kind of thing that
  separates people who've read about RPKI from people who've run it.
- Prepend AS-path on the rogue announcement and confirm it changes nothing once the
  filter is on. Origin validation doesn't care about path length.

---

## Phase 4 — Detection, not just prevention

Prevention is one job. Noticing is the other, and it's the one that's actually yours in a
SOC or NOC.

On `transit`, turn on update logging:

```
configure terminal
router bgp 65001
 neighbor 10.99.0.4 update-source-tracking
end
```

(If your FRR build rejects that, use `debug bgp updates in` instead, then
`show logging` / `docker logs bgp-transit`.)

Now re-run the hijack from Phase 2 while watching:

```bash
docker logs -f bgp-transit
```

Then answer these, in writing:

1. What field in the UPDATE would let an automated system flag this as suspicious
   **without** RPKI?
2. If you were monitoring 50,000 prefixes, what would you alert on — and what would your
   false positive rate look like when a legitimate customer starts announcing a new
   more-specific for traffic engineering?
3. How long would a hijack have to last before it mattered? Minutes? Seconds?

Question 2 is the actual job. Real BGP monitoring is a false-positive problem, not a
detection problem — detecting an origin change is trivial, deciding which origin changes
are worth waking someone up for is not.

**Optional and worth it:** point a browser at BGPStream or the RIPE RIS live feed and look
at real hijack alerts from the last week. You now know exactly what you're looking at.

---

## Phase 5 — Bring OPNsense in for real

Only after Phases 1–4 make sense. This one touches production, so read the whole phase
before typing anything.

### 5a. NetFlow export (safe, do this first)

This is read-only and is the single highest-value thing in the whole lab for ISP security
work, because flow analysis *is* the job.

1. OPNsense → **Reporting → NetFlow**. Set listening interfaces (your VLANs), destination
   `<unraid-ip>:2055`, version 9.
2. Stand up a collector on Unraid. Since you already run Prometheus + Grafana, the
   lowest-friction path is a collector that exposes Prometheus metrics — `pmacct` or
   `goflow2` both work; goflow2 → Loki/Prometheus is the smaller lift.
3. Build a Grafana dashboard with: top talkers by bytes, top destination ASNs,
   flows-per-second by VLAN, and new-destination-ASN-first-seen.

That last panel is a genuine security control. It's how you catch a compromised IoT device
beaconing somewhere it has never talked to before — and given you already have an IoT VLAN
segmented off, you have the exact scenario worth watching.

### 5b. OPNsense as a real BGP peer (do this deliberately)

**Read first:** you are adding a routing daemon to your edge firewall. The failure mode is
losing internet for the whole house. Do it when nobody needs the network, know how to get
console access to the OPNsense box, and take a config backup before you start
(System → Configuration → Backups → Download).

1. Install the **os-frr** plugin (System → Firmware → Plugins).
2. Enable FRR, enable BGP, set local AS `65005` and a router ID.
3. Peer with the transit container. The lab bridge is internal to Docker, so you need to
   either publish it or — cleaner — put a fifth FRR container on a macvlan interface in a
   VLAN OPNsense can already reach. You've done macvlan work on this box for the ARR
   stack, so this is familiar ground.
4. **Filter inbound.** Configure a prefix-list that accepts *only* 203.0.113.0/24 and
   198.51.100.0/24 and denies everything else. Do this *before* the session comes up, not
   after. A lab AS announcing a default route to your edge firewall is exactly how you
   lose an evening.
5. Verify with `show ip bgp` in the OPNsense FRR shell, and confirm your default route to
   your actual ISP is untouched.

Step 4's prefix-list is not a lab safety rail bolted on for the exercise — it is what
every real BGP session on the internet should have and what a great many still don't.
That gap is most of why Phases 2 and 3 exist.

---

---

## Phase 6 — RTBH, and Phase 7 — FlowSpec

Continued in **[PHASE6-RTBH.md](PHASE6-RTBH.md)**.

Phases 1–3 covered hijacking and prevention. Phase 6 covers the other half of carrier
security: signalling your upstream provider to drop a DDoS *before* it saturates your link,
using the BGP session you already have. The scaffolding is already staged in the `transit`
and `isp` configs.

Phase 7 sketches BGP FlowSpec as a stretch goal — it needs ExaBGP, since FRR can receive
FlowSpec but not originate it.

---

## Teardown

```bash
docker compose down
```

Nothing persists outside the container network. If you did Phase 5b, disable the FRR
plugin on OPNsense separately — compose teardown obviously doesn't touch it.

---

## Troubleshooting

**BGP sessions stuck in `Active` or `Idle`**
Check the containers can reach each other: `docker exec bgp-customer ping -c2 10.99.0.1`.
If ping works and BGP doesn't, it's almost always the missing `no bgp ebgp-requires-policy`
— FRR 7.4+ implements RFC 8212 and silently discards all eBGP routes unless policy is
explicitly configured or that knob is set. It's already in every config here, but if you
rebuild one by hand, that's the line you'll forget.

**`rpki` is not a recognized command**
The `-M rpki` module didn't load. Check `docker exec bgp-customer ls /usr/lib/frr/modules/`.
If `bgpd_rpki.so` isn't there, your `frrouting/frr:latest` build lacks it — pin to a
specific release tag instead (check Docker Hub for current `v10.x` tags) or build from
the FRR Dockerfile with rtrlib enabled. **If you can't get it working, skip Phase 3's
route-map and substitute a manual prefix-list** that permits only `203.0.113.0/24` from
AS65002. You lose the cryptographic-validation lesson but keep the filtering lesson, which
is the more broadly applicable of the two.

**`show rpki prefix-table` is empty**
The RTR session isn't up. `docker logs bgp-rpki` should show it serving. Confirm the
`vrps.json` mount worked: `docker exec bgp-rpki cat /vrps.json`. Note StayRTR is strict
about the JSON schema — a trailing comma will make it start and serve nothing.

**Config edits don't survive a container restart**
Expected. Changes made in `vtysh` live in memory; the file mounts are read at start. Either
edit the `.conf` files on disk and `docker compose restart <svc>`, or `write memory` inside
vtysh — the latter needs the mount to be writable and the file owned by the `frr` user, so
editing on disk is the less annoying path.

**Everything is broken and you want to start over**

```bash
docker compose down && docker compose up -d
```

The configs on disk are the source of truth, so this always returns you to a known state.
