ObjC.import("Foundation");

function endpoint(url) {
  const parts = $.NSURLComponents.componentsWithString($(url));
  if (!parts) return null;
  const scheme = ObjC.unwrap(parts.scheme)?.toLowerCase();
  const host = ObjC.unwrap(parts.host)?.toLowerCase();
  if (!host || !["http", "https"].includes(scheme)) return null;
  const port = ObjC.unwrap(parts.port) ?? (scheme === "https" ? 443 : 80);
  return JSON.stringify([scheme, host, port]);
}

function openChrome(url) {
  const wanted = endpoint(url);
  if (!wanted) throw new Error("Use a complete HTTP or HTTPS URL.");
  const chrome = Application("com.google.Chrome");
  let windows = chrome.windows();
  for (const win of windows) {
    const tabs = win.tabs();
    for (let index = 0; index < tabs.length; index++) {
      if (endpoint(tabs[index].url()) !== wanted) continue;
      win.activeTabIndex = index + 1;
      win.minimized = false;
      win.index = 1;
      chrome.activate();
      return { action: "focused" };
    }
  }
  if (!windows.length) {
    chrome.windows.push(chrome.Window());
    windows = chrome.windows();
    windows[0].tabs()[0].url = url;
    windows[0].activeTabIndex = 1;
  } else {
    const win = windows[0];
    win.tabs.push(chrome.Tab({ url }));
    win.activeTabIndex = win.tabs().length;
  }
  windows[0].minimized = false;
  windows[0].index = 1;
  chrome.activate();
  return { action: "opened" };
}

function run(args) {
  return JSON.stringify(openChrome(args[0]));
}
