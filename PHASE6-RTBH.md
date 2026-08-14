# Phase 6 — Remotely Triggered Black Hole (RTBH)

Prerequisite: Phases 1–3 of the main [README](README.md). You need working BGP sessions
and a feel for `show ip bgp` before this makes sense.

**Time: 2–4 hours.** Nothing here touches your real network — it all lives in the Docker
bridge.

---

## The problem RTBH solves

A host in your network is getting hit with 40 Gbps of UDP flood. Your uplink is 10 Gbps.

Filtering at your own firewall is useless — the traffic has *already crossed the link you
are trying to protect*. The link is the thing that's saturated. By the time packets reach
your edge, everything behind that link is already down, including the 99% of your traffic
that has nothing to do with the attack.

So you need to drop it **upstream**, at your provider's edge, before it enters your pipe.
But you can't log into your provider's routers, and nobody wants to open a ticket and wait
40 minutes during an outage.

RTBH is the answer: you signal your provider over the BGP session **you already have**,
using a community tag they've pre-agreed to honor. Response time is one BGP update —
sub-second. No phone call, no ticket, no human.

The tradeoff is brutal and worth sitting with: **you are completing the denial of service
for the attacker.** The target IP becomes globally unreachable. You're choosing to sacrifice
one host to save the other 65,535 addresses behind that link. That's a triage decision, and
knowing when it's the right call is judgment, not configuration.

---

## Step 1 — Arm the provider

The provider side is always configured *in advance*. When an attack is happening is the
wrong time to be writing route-maps.

On `transit` (AS65001), the scaffolding already exists in the config — a discard route to
`192.0.2.1`, two community-lists, and the `RTBH-IN` route-map. Read it first:

```bash
docker exec -it bgp-transit vtysh
```

```
show run
show ip route 192.0.2.1
```

That static should show as blackhole/unreachable. Now apply the policy to the customer
session:

```
configure terminal
router bgp 65001
 address-family ipv4 unicast
  neighbor 10.99.0.2 route-map RTBH-IN in
 exit-address-family
end
```

**This is the part real providers get wrong.** Applying RTBH policy to a customer session
means that customer can now blackhole any prefix they announce. If you don't *also* filter
which prefixes they're allowed to announce, a customer can blackhole someone else's address
space. Think about how that combines with the hijack you did in Phase 2 — announce a prefix
you don't own, tag it blackhole, and you've weaponized your provider's own DDoS protection
into a DoS tool. Prefix filtering is not optional here; it's load-bearing.

## Step 2 — Trigger the blackhole

The host `203.0.113.50` is under attack. On `isp` (AS65002), the legitimate holder:

```bash
docker exec -it bgp-isp vtysh
```

```
configure terminal
router bgp 65002
 address-family ipv4 unicast
  network 203.0.113.50/32 route-map SET-BLACKHOLE
  neighbor 10.99.0.1 send-community
 exit-address-family
end
```

Confirm you're announcing what you think you are:

```
show ip bgp 203.0.113.50/32
show bgp ipv4 unicast neighbors 10.99.0.1 advertised-routes
```

You should see the /32 with communities `65535:666 65001:666 no-export`.

## Step 3 — Verify the drop

Back on `transit`:

```
show ip bgp 203.0.113.50/32
```

Look at the next-hop. It should be **192.0.2.1**, not 10.99.0.2. The route-map rewrote it
on the way in. Now:

```
show ip route 203.0.113.50
```

Blackhole. Traffic to that host now dies at the provider edge and never touches the
customer link — which is the entire point.

Confirm the containment worked, on `customer` (AS65003):

```
show ip bgp 203.0.113.50/32
```

**Nothing.** The `no-export` community stopped transit from passing it to its other
customers. Without that, you'd have blackholed the host across every network downstream of
your provider.

> **One honest note about what you're observing.** Every prefix in this lab is a blackhole
> static, so you're watching the *control plane* — the routing decision — not actual
> packets being dropped. That's not a shortcut; RTBH genuinely is a control-plane mechanism,
> and "did the FIB entry become a discard" is exactly what an operator checks. But don't
> come away thinking you watched traffic die. You watched the decision to kill it.

## Step 4 — Withdraw

Attacks end. Practice the cleanup, because doing it under pressure at 3am is when people
fat-finger production:

```
configure terminal
router bgp 65002
 address-family ipv4 unicast
  no network 203.0.113.50/32
 exit-address-family
end
```

Verify on `transit` that the route is gone and the host is reachable again.

**Real operations question:** how do you decide when to withdraw? Withdraw too early and
the attack resumes. Withdraw too late and you've extended your own outage. Most shops
automate the trigger and leave the withdrawal manual, precisely because that judgment is
hard to encode.

---

## Exercises

Work these in order. They get progressively closer to real operational problems.

**1. Blackhole the wrong thing.** From `rogue` (AS65004), announce `203.0.113.50/32` with
the blackhole community. Does transit accept it? What does that tell you about combining
RTBH with the prefix filtering from Phase 3? Write down the attack chain.

**2. Break containment.** Remove `no-export` from `SET-BLACKHOLE` on the isp, re-announce,
and check `customer` again. Now the blackhole has escaped into a network that never asked
for it. This is a real and recurring class of outage.

**3. Granularity.** RTBH takes the whole host offline. What if the attack targets port 443
and you need SSH to stay up? RTBH can't do that — which is the exact gap Phase 7 fills.

**4. Source-based RTBH (S/RTBH).** Everything above is *destination*-based: you kill traffic
*to* the victim. Source-based instead drops traffic *from* known attacker addresses, keeping
the victim online. It relies on uRPF — the router drops packets whose *source* has a
discard route. Look up loose-mode uRPF and work out why S/RTBH is far less commonly deployed.
Hint: it involves how many sources a modern botnet has.

**5. Automate it.** Write a script that takes an IP and triggers the blackhole via vtysh.
That's the beginning of a real DDoS mitigation pipeline, and it's the Python practice your
CCNA plan wants in Week 7 anyway.

---

## Phase 7 — BGP FlowSpec (stretch, separate session)

**Read this before starting: FRR can *receive* FlowSpec rules but cannot originate them.**
So you can't do this with the containers you already have — you need **ExaBGP** as the
controller. Budget 3–5 hours and expect more friction than Phase 6.

FlowSpec (RFC 8955) fixes exercise 3. Instead of "drop everything to this IP," you
distribute an actual 5-tuple filter over BGP: *drop UDP traffic to 203.0.113.50 port 443
with packet length 800–1200*. The victim stays up; only the attack traffic dies.

Rough shape:
1. Add an ExaBGP container peering with `transit` as a new AS, with `family ipv4 flow-vpn`.
2. Define a flow rule in ExaBGP's config — match destination, protocol, port; action
   `discard` or `rate-limit`.
3. On the FRR side, enable `address-family ipv4 flowspec` and confirm receipt with
   `show bgp ipv4 flowspec detail`.
4. On Linux, FRR installs received FlowSpec rules into netfilter — so `iptables -L` on the
   container shows the actual filter that BGP just delivered. That moment, watching a
   firewall rule arrive over a routing protocol, is the one worth having.

**Why FlowSpec is less deployed than it should be:** it's a beautiful mechanism that lets a
peer install filters in *your* routers, which is exactly why operators are nervous about
accepting it. Most providers accept FlowSpec only from customers, heavily validated, or not
at all. Knowing that tension — and being able to explain it — is more valuable in an
interview than the config itself.

---

## Troubleshooting

**The /32 isn't installed as a blackhole on transit**
Check next-hop resolution first: `show ip route 192.0.2.1` and `show bgp nexthop`. FRR must
resolve the rewritten next-hop through the discard static before it will install the route.
If the next-hop shows unresolved, the BGP route stays in the table but never reaches the
FIB. Confirm the static exists and that `show ip bgp 203.0.113.50/32` actually shows
192.0.2.1 rather than the original peer address — if it shows the peer address, the
route-map didn't match and the problem is upstream in step 1.

**Communities aren't arriving**
`show ip bgp 203.0.113.50/32` on transit should list them. If empty, the sender isn't
including them — check `neighbor 10.99.0.1 send-community` on the isp. FRR sends standard
communities by default, but being explicit costs nothing and this is the first thing to
rule out.

**The route-map matches nothing**
`show bgp community-list BLACKHOLE-WELLKNOWN` and confirm the community-list is populated.
Watch for the classic mistake of writing `65535:666` as `65535:0666`.

**Start over**

```bash
docker compose down && docker compose up -d
```
