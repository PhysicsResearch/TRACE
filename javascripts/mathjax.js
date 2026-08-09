window.MathJax = {
  tex: {
    inlineMath: [["\\(", "\\)"], ["$", "$"]],
    displayMath: [["\\[", "\\]"], ["$$", "$$"]],
    processEscapes: true,
    processEnvironments: true
  },
  options: {
    ignoreHtmlClass: ".*",
    processHtmlClass: "arithmatex"
  }
};

document.querySelectorAll('.arithmatex').forEach(function(element) {
  MathJax.typesetPromise([element]);
});
