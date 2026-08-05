---
name: external-rfc-9309-robots-exclusion-protocol-ietf-standard
type: reference
source: https://www.rfc-editor.org/rfc/rfc9309.html
source_sha: 97e53ec45577713c
fetched_at: 2026-08-05T03:49:53Z
last_verified: 2026-08-05
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: RFC 9309 Robots Exclusion Protocol IETF standard user-agent matching precedence
---

## reference · Robots Exclusion Protocol
* The protocol language consists of rule(s) and group(s) in a file named "robots.txt".
* A group is one or more user-agent lines followed by one or more rules, terminated by a user-agent line or end of file.
* The last group may have no rules, which means it implicitly allows everything.
* Crawlers MUST use case-insensitive matching to find the group that matches the product token.
* If there is more than one group matching the user-agent, the matching groups' rules MUST be combined into one group and parsed.
* If no matching group exists, crawlers MUST obey the group with a user-agent line with the "*" value, if present.
* The product token MUST contain only uppercase and lowercase letters ("a-z" and "A-Z"), underscores ("_"), and hyphens ("-").
* The product token SHOULD be a substring of the identification string that the crawler sends to the service.
* The identification string SHOULD describe the purpose of the crawler.
* Crawlers MUST obey the rules of the group that matches the product token.
* Rules are defined by a key-value pair on a line, with "allow" or "disallow" as the key.
* Path patterns MUST be valid URI path patterns, starting with a "/".
* Crawlers MUST parse the rules according to the formal syntax defined in the specification.
Sources: https://www.rfc-editor.org/rfc/rfc9309.html
