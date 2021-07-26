// Helpers called on the main test HTMLs.
// Scripts in `send()` arguments are evaluated on the executors
// (`executor.html`), and helpers available on the executors are defined in
// `executor.html`.

const origins = {
    SameOrigin:
    location.protocol === 'http:' ?
        'http://{{host}}:{{ports[http][0]}}' :
        'https://{{host}}:{{ports[https][0]}}',
    SameSite:
    location.protocol === 'http:' ?
        'http://{{host}}:{{ports[http][1]}}' :
        'https://{{host}}:{{ports[https][1]}}',
    CrossSite:
        location.protocol === 'http:' ?
        'http://{{hosts[alt][www]}}:{{ports[http][0]}}' :
        'https://{{hosts[alt][www]}}:{{ports[https][0]}}'
};

const executorPath =
  '/html/browsers/browsing-the-web/back-forward-cache/resources/executor.html?uuid=';
const backPath =
  '/html/browsers/browsing-the-web/back-forward-cache/resources/back.html';

// Asserts that the executor `target` is (or isn't, respectively)
// restored from BFCache. These should be used in the following fashion:
// 1. Call prepareNavigation() on the executor `target`.
// 2. Navigate the executor to another page.
// 3. Navigate back to the executor `target`.
// 4. Call assert_bfcached() or assert_not_bfcached() on the main test HTML.
//
// These methods (and getBFCachedStatus()) should be called after the send()
// Promise in Step 1 is resolved, but we don't need to wait for the completion
// of the navigation and back navigation in Steps 2 and 3,
// because the injected scripts to the executor are queued and aren't executed
// between prepareNavigation() and the completion of the back navigation.
async function assert_bfcached(target) {
  const status = await getBFCachedStatus(target);
  assert_implements_optional(status === 'BFCached', 'Should be BFCached');
}

async function assert_not_bfcached(target) {
  const status = await getBFCachedStatus(target);
  assert_implements_optional(status !== 'BFCached', 'Should not be BFCached');
}

async function getBFCachedStatus(target) {
  const resp = await target.executeScript(() => [window.loadCount, window.isPageshowFired]);
  const [loadCount, isPageshowFired] = resp.toLocal();
  if (loadCount === 1 && isPageshowFired === true) {
    return 'BFCached';
  } else if (loadCount === 2 && isPageshowFired === false) {
    return 'Not BFCached';
  } else {
    // This can occur for example when this is called before first navigating
    // away (loadCount = 1, isPageshowFired = false), e.g. when
    // 1. sending a script for navigation and then
    // 2. calling getBFCachedStatus() without waiting for the completion of
    //    the script on the `target` page.
    assert_unreached(
      `Got unexpected BFCache status: loadCount = ${loadCount}, ` +
      `isPageshowFired = ${isPageshowFired}`);
  }
}
