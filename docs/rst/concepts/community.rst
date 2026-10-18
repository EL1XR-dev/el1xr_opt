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

.. graphviz::
   :align: center
   :alt: Members of one zone share electricity through a pool in which what is shared out equals what is shared in, and each member still trades with the grid through its retailer.

   digraph community {
     graph [rankdir=LR, nodesep=0.3, ranksep=0.8, fontname="Helvetica"];
     node  [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, fillcolor="#ffffff", color="#888888"];
     edge  [color="#555555", arrowsize=0.7, fontname="Helvetica", fontsize=9];
     grid [label="Grid, through each\nmember's retailer", fillcolor="#fff3e0", color="#ef6c00"];
     subgraph cluster_z {
       label="One zone"; color="#6a1b9a"; fontcolor="#6a1b9a"; style=rounded;
       a    [label="Member A\nsurplus (e.g. solar)"];
       b    [label="Member B\ndemand"];
       c    [label="Member C"];
       pool [label="Sharing pool\nshared out = shared in\neEleCommunityPool", shape=ellipse, fillcolor="#e1bee7", color="#6a1b9a"];
     }
     a -> pool [label="vEleShareOut"];
     pool -> b [label="vEleShareIn"];
     c -> pool [dir=both, label="in or out"];
     grid -> {a b c} [dir=both, color="#ef6c00"];
   }

- Two per-member variables, ``vEleShareIn`` and ``vEleShareOut``, carry electricity
  shared into and out of a member.
- A per-zone pool-conservation constraint (``eEleCommunityPool``) requires that, within
  a zone, what is shared in equals what is shared out -- sharing is internal and
  lossless, it neither creates nor destroys energy:

  .. math::
     \sum_{\eltraderindex \in \zoneindex} \veleshareout_{\periodindex,\scenarioindex,\timeindex,\eltraderindex}
     = \sum_{\eltraderindex \in \zoneindex} \velesharein_{\periodindex,\scenarioindex,\timeindex,\eltraderindex}
     \quad \forall \periodindex,\scenarioindex,\timeindex,\zoneindex

  This pool balance applies only within a zone that has at least two community members;
  zones with fewer than two members are skipped, because a single member has no one to
  share with.
- The retail balance ``eEleRetNodeBalance`` (see :doc:`constraints`) gains
  :math:`+ \velesharein_{\periodindex,\scenarioindex,\timeindex,\eltraderindex}
  - \veleshareout_{\periodindex,\scenarioindex,\timeindex,\eltraderindex}` on its supply
  side when the layer is on, so a member can meet demand from a neighbour's surplus
  instead of buying from the grid.

Because the sharing terms net to zero across the zone and only re-route energy that is
already produced, the community optimum is never worse than the members acting alone,
and is strictly better when the retail spread makes local sharing cheaper than trading
with the grid.
