# Word macro client

The installed `DQWordPublishing.bas` template is a provider-neutral Word VBA client for the public
loopback bridge. Import it into Word's VBA editor, start a local
`WordPublishingBridge` with a reviewed `QuestionSet`, and use the `DQ_*`
commands from the macro list.

The client supports inserting a managed reference block, refreshing one block,
refreshing all blocks in document order, compose borders, final rendering, and
single-block rollback when a bridge response is stale or fails. The bridge
contract is JSON-only and credentials-free. The macro does not execute text
from the document and does not accept a remote origin.

The module is a template rather than a signed Microsoft Office add-in. Test it
with the Word version and macro security policy used by your organization
before enabling it on working documents.

Export the exact template shipped with your installed package:

```bash
dq word-macro -o DQWordPublishing.bas
```
