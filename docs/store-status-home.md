# Store status home

[简体中文](zh-CN/store-status-home.md)

The default `/workbench` page shows a simple store status, one short explanation and up to three figures from the latest saved check. The conversation stays under **More → Talk to your assistant**; existing review and analysis pages remain available to administrators.

Use the language selector for English or Chinese. The selected language is remembered in this browser. With multiple stores, choose the store in the header. The freshest available evidence is selected initially unless an explicit valid store link is supplied.

## Understand the state

- **Checking your store** requires a running receipt for this store updated/started within 120 seconds. Polling and visual animation alone never count as a running task.
- **Your latest check is ready** means a saved check is available, not that an AI continuously operates the store.
- **A few things need a look** links to observations worth reviewing; they are not fixes already performed or separately approved actions.
- **Your store check needs attention** means a failed task newer than the saved data exists.
- **Time for a fresh check** marks data older than 24 hours. The source timestamp is displayed in the Romania time zone.
- **Ready when your store is** and connection errors have explicit empty/error views; unknown numbers use a dash with an accessible explanation, never zero.

The current collector writes final receipts. Consequently it normally shows completed/waiting/failed rather than live progress. No new worker, scheduler, store-write permission or automatic action is enabled by the page.

The carousel rotates short explanations, not fabricated activity. Pause it or move manually using its controls. Rotation stops when the page is hidden, when leaving this route and when the system requests reduced motion. Reduced-motion users retain manual navigation. Live reads refresh every 30 seconds while this route and browser tab are visible. Old responses cannot replace another store's information; failed reads clear its metrics.

## Public demo

The published demo starts on the same shared status presentation. Its visible demo notice identifies the data and finite looping workflow as synthetic. The headline may say “Taking care of your store”, but the demo has no network/store connection, model execution or marketplace writes. Figures stay tied to the fixed illustrative dataset rather than increasing with animation.

## Existing deployments

Update the identified existing service from merged source and build/copy its matching frontend. Preserve its environment, credentials, data paths, scheduled tasks and marketplace-write gates. A separate empty test installation is not a replacement for the real runtime. Restart only the identified service and verify its authentication and original store records after updating. Keep machine paths and diagnostic records in private deployment/data locations, not this repository.

## Naming compatibility

Visible product branding uses `store-ops`. Existing `IVYEA_OPS_*` configuration keys, credential target `IvyeaOps/eMAG/RO`, internal module names, API/tool identifiers and existing scheduled-task/data names remain compatible. A repository rename is not a data or credential migration. Upstream license notices and actual release references retain their original names. Replace those contracts only through a separate versioned migration, not a global search-and-replace.

## Sharing language

Use `?lang=zh-CN` to share the demo in Chinese, or `?lang=en` for English. An explicit URL language takes priority over a saved manual choice, then the first supported browser language is used; other languages fall back to English. Changing language also updates the current URL so it can be shared. The demo keeps only a short illustrative-data notice; the production view retains source time and material error/staleness states.
