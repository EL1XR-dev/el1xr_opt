Energy community
================

The energy-community layer (``oM_Community.py``) lets retailers (members) in the same
zone share locally generated electricity with each other before importing from or
exporting to the grid. Sharing avoids the retail buy/sell spread, so it lowers the
total community cost without changing what each member physically does.

It is **off by default** and enabled with the option flag ``IndBinCommunity``
(``pOptIndBinCommunity``); cases that do not set it are unchanged.

How it works
------------

- Two per-member variables, ``vEleShareIn`` and ``vEleShareOut``, carry electricity
  shared into and out of a member.
- A per-zone pool-conservation constraint (``eEleCommunityPool``) requires that, within
  a zone, what is shared in equals what is shared out -- sharing is internal and
  lossless, it neither creates nor destroys energy. This pool balance applies only
  within a zone that has at least two community members; zones with fewer than two
  members are skipped, because a single member has no one to share with.
- The retail balance ``eEleRetNodeBalance`` gains ``+ vEleShareIn - vEleShareOut`` when
  the layer is on, so a member can meet demand from a neighbour's surplus instead of
  buying from the grid.

Because the sharing terms net to zero across the zone and only re-route energy that is
already produced, the community optimum is never worse than the members acting alone,
and is strictly better when the retail spread makes local sharing cheaper than trading
with the grid.
