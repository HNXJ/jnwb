// Posts the page's palette to each interactive figure. The figure's HTML switches its Plotly template
// on the message, and it is light until the first message arrives. The figures are served from
// another origin, so the message names that origin as its target and nothing else reads the page.
(function () {
  var FIGURES = "https://hnxj.github.io/jnwb/figures/";

  function scheme() {
    return document.body.getAttribute("data-md-color-scheme") === "slate" ? "dark" : "light";
  }

  function post() {
    var frames = document.querySelectorAll('iframe[src^="' + FIGURES + '"]');
    frames.forEach(function (frame) {
      if (frame.contentWindow) {
        frame.contentWindow.postMessage({ type: "jnwb-scheme", scheme: scheme() }, "https://hnxj.github.io");
      }
    });
  }

  document.addEventListener("DOMContentLoaded", post);
  // A figure loads after the page; the palette toggle changes the body's attribute.
  document.addEventListener("load", post, true);
  new MutationObserver(post).observe(document.body, {
    attributes: true,
    attributeFilter: ["data-md-color-scheme"]
  });
  if (window.document$) {
    window.document$.subscribe(post);
  }
})();
