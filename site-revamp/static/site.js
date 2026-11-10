/* Progressive enhancement: a copy button on every code block. The site reads without it. */
(() => {
  const ro = document.documentElement.lang === "ro";
  const copyText = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      return false;
    }
  };
  document.querySelectorAll("figure.code").forEach((figure) => {
    const head = figure.querySelector(".code-head");
    const code = figure.querySelector("pre code");
    if (!head || !code) {
      return;
    }
    const button = document.createElement("button");
    button.type = "button";
    button.className = "copy";
    button.textContent = ro ? "Copiază" : "Copy";
    button.addEventListener("click", async () => {
      if (!(await copyText(code.textContent))) {
        return;
      }
      const previous = button.textContent;
      button.textContent = ro ? "Copiat" : "Copied";
      window.setTimeout(() => {
        button.textContent = previous;
      }, 1500);
    });
    head.appendChild(button);
  });
})();
