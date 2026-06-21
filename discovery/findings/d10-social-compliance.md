# Source: X / Reddit social compliance review (social-compliance)

- **Reachable:** yes, for public terms, policy, billing, changelog, and rate-limit documentation only.
- **Access method:** documentation-only compliance review. No X or Reddit data/content endpoints were called.
- **Auth required:** none for the public documentation reviewed. Any future X or Reddit API use requires approved platform access and must follow source-specific access tiers, terms, and rate limits.
- **requires_secret:** true for any future API use; false for this documentation review.
- **License / terms URL:** X usage/billing `https://docs.x.com/x-api/fundamentals/post-cap`; X rate limits `https://docs.x.com/x-api/fundamentals/rate-limits`; X changelog `https://docs.x.com/changelog`; X Developer Agreement `https://docs.x.com/developer-terms/agreement`; X Developer Policy `https://docs.x.com/developer-terms/policy`; Reddit Data API Terms `https://redditinc.com/policies/data-api-terms`; Reddit Developer Terms `https://redditinc.com/policies/developer-terms`.
- **Allowed use (1 line):** Social signals may enter this project only as compliant, timestamped aggregates such as counts, sentiment scores, trend flags, or availability flags; never store raw user text or use raw user content as training data.
- **Endpoint(s) / URL(s) probed:** Public documentation pages listed above only. No X posts, X search, Reddit posts, Reddit comments, subreddits, users, listings, or other content endpoints were requested.
- **Schema (key columns/fields):** not applicable. A future compliant aggregate table should contain fields like `source`, `observed_at`, `team_id`, `match_id`, `window_start`, `window_end`, `metric_name`, `metric_value`, and `method_version`, not raw post/comment text.
- **Row / record count in sample:** 0. No social records were pulled.
- **Date range / freshness (latest record date):** not applicable. Documentation pages were reviewed on 2026-06-21.
- **Frozen?** no. These are live policy/API surfaces and must be rechecked before any Phase 3 implementation.
- **2026 World Cup relevance:** medium. Social platforms can provide optional crowd/injury/lineup context, but only after the Elo-first probability path is proven and only as compliant aggregates.
- **Gotchas:** X pricing and self-serve access changed in 2026 toward pay-per-usage; current endpoint pricing is exposed through the Developer Console rather than a static public price table. Reddit explicitly blocks using user content / Reddit data to train ML, AI, large-language, or algorithmic models without permission. Both platforms can suspend or block access for rate-limit or terms violations.
- **Recommended phase:** 3
- **Retention recommendation:** raw_retention_days=0 for X and Reddit user text. bronze_retention_days=365 for compliant aggregates only, with `observed_at`, source attribution, metric definitions, and no raw post/comment bodies.
- **Sample saved at:** none.
- **Status:** usable with strict caveats for Phase 3 aggregate-only signals; no raw-content ingestion is approved.

## Documentation reachability

The public documentation pages were accepted only after validating HTTP 200 plus `text/html` content type and page shape (`<title>` / `<h1>`), not by HTTP status alone.

| URL | Validation result |
| --- | --- |
| `https://docs.x.com/changelog` | 200, `text/html; charset=utf-8`, title `X API changelog and release notes - X`, h1 `X API changelog and release notes` |
| `https://docs.x.com/x-api/fundamentals/post-cap` | 200, `text/html; charset=utf-8`, title `Usage and Billing - X`, h1 `Usage and Billing` |
| `https://docs.x.com/developer-terms/policy` | 200, `text/html; charset=utf-8`, title `X Developer Policy - X`, h1 `X Developer Policy` |
| `https://redditinc.com/policies/data-api-terms` | 200, `text/html; charset=UTF-8`, title `Data API Terms` |
| `https://redditinc.com/policies/developer-terms` | 200, `text/html; charset=UTF-8`, title `Developer Terms` |

## X API rules and cost model

Source URLs: `https://docs.x.com/x-api/fundamentals/post-cap`, `https://docs.x.com/x-api/fundamentals/rate-limits`, `https://docs.x.com/changelog`, `https://docs.x.com/developer-terms/agreement`, `https://docs.x.com/developer-terms/policy`.

Current X API v2 billing is credit-based pay-per-usage: developers buy credits, different endpoints have different per-request costs, and usage is tracked at the app level. Public docs state that pay-per-usage plans have a monthly cap of 2 million Post reads; higher-volume needs should use Enterprise. The public docs direct current endpoint/operation pricing to the Developer Console, so do not hard-code dollar figures from older static pricing tables.

X's 2026 changelog says Pay-Per-Use officially launched on 2026-02-06, Public Utility Apps continue to receive free scaled access, recently active Legacy Free tier users receive a one-time voucher, Basic and Pro remain available, and existing subscribers can opt in to Pay-Per-Use.

| Tier / model | Cost model | What it allows at a high level | Key restriction for this project |
| --- | --- | --- | --- |
| Free / Public Utility / Legacy Free | Limited free access where approved; legacy free users received a one-time voucher under the Pay-Per-Use launch note. | Narrow approved use cases, public-utility exceptions, or low-volume/legacy experimentation. | Not a basis for production collection. Treat as unavailable unless X explicitly approves the exact use case. |
| Pay-Per-Use | Credit-based, per-endpoint/per-operation usage, tracked in Developer Console. | Self-serve usage for indie builders, startups, hobbyists, and apps within the monthly cap. | Requires budget guards, endpoint allowlists, rate-limit handling, and no raw text retention unless separately approved. |
| Basic | Paid self-serve subscription remains available. | Hobbyist, commercial prototyping, initial development, early-stage X integrations, and limited end-user apps. | Not enough for broad data products or large-scale monitoring. Any use must match the approved use-case description. |
| Pro | Paid self-serve subscription remains available. | Higher self-serve development/prototyping than Basic, still within limited end-user / early-stage scope. | Still self-serve; X may require Enterprise if the use exceeds scope. |
| Enterprise | Custom pricing and contract. | High-volume needs, custom rate limits, dedicated support, volume discounts, and broader/complete data access where contracted. | Required for use beyond self-serve scope or if X requires it after review. |

Restrictions relevant to the project:

- X Developer Agreement grants API/content use only subject to compliance and explicit approval for analysis of X Content.
- X Developer Agreement prohibits using the X API or X Content to fine-tune or train a foundation or frontier model.
- X Developer Agreement and Policy require the project to use the tier matching its use case, keep keys private, comply with all policies, and notify/receive approval for substantive use-case changes.
- X rate limits are per endpoint, often per 15-minute or 24-hour window, and must be monitored through `x-rate-limit-limit`, `x-rate-limit-remaining`, and `x-rate-limit-reset`.
- X restricts redistribution of X Content; future aggregate tables must not become a downloadable raw-post corpus.

## Reddit rules and commercial posture

Source URLs: `https://redditinc.com/policies/data-api-terms`, `https://redditinc.com/policies/developer-terms`.

Reddit's Data API Terms are the hard stop for this project: user content may not be used for training machine-learning or AI models without express permission from the applicable rightsholders. The same terms say Reddit may set and enforce API limits, may charge fees for future access, and requires a separate agreement for commercial purposes, research beyond rate limits, or other non-expressly-permitted uses.

Reddit's Developer Terms are broader and stricter for the Developer Platform: Reddit can suspend or block access for circumventing rate limits, restricts business/monetized use unless permitted or approved in writing, requires a separate agreement for commercial use or research beyond rate limits, and prohibits accessing or using Reddit Services and Data through API/indexing/caching/crawling to train large language, artificial intelligence, or other algorithmic models without Reddit's permission.

Allowed Reddit use for this project is therefore aggregate-only and permission-bound:

- Allowed only after Phase 3 review: timestamped counts, rates, sentiment labels, moderation-safe flags, or other aggregate metrics created under the applicable API terms.
- Not allowed: storing post/comment bodies, creating a Reddit text corpus, training or fine-tuning any ML/AI model on Reddit user content, redistributing Reddit content, or using Reddit data commercially without the required agreement.
- Any future Reddit connector must enforce raw text retention of zero days and must write tests proving raw user text cannot enter training datasets.

## Governing decision

Social/news enters the system only as compliant, timestamped aggregates. The approved aggregate surface is counts, sentiment scores, trend flags, entity-linked availability flags, and similar metrics with source, time window, and method metadata. Raw user text is never stored, redistributed, or used as training data.

Both X and Reddit are deferred to Phase 3. Nothing from this D10 review is approved for Phase 1 ingestion, Phase 2 market/odds benchmarking, or the core probability path.

Reddit user content cannot be used to train ML/AI models without permission from the applicable rightsholders and, under Developer Terms, Reddit permission for model-training access/use. Aggregates only.

Nothing here touches the probability path. The master plan's no-LLM / no-social-probability rule remains intact: social aggregates may become optional explanatory context only after the Elo-first model earns its place and after a fresh terms review.
