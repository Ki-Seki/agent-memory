// The site's two behaviours: a border under the header once the page scrolls, and copy buttons on commands.
const COPY = '<svg class="i" viewBox="0 0 24 24" aria-hidden="true"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>';
const DONE = '<svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>';

const top = document.querySelector(".top");
const onScroll = () => top?.classList.toggle("scrolled", scrollY > 8);
addEventListener("scroll", onScroll, { passive: true });
onScroll();

// every command block gets a copy button; comments (after #) are left out of what is copied
for (const block of document.querySelectorAll(".cmd, pre.code, .docs pre:not(.file)")) {
  const button = document.createElement("button");
  button.className = "copy";
  button.type = "button";
  button.setAttribute("aria-label", "Copy");
  button.innerHTML = COPY;
  button.addEventListener("click", async () => {
    const text = block.querySelector("code").innerText.split("\n").map((l) => l.replace(/\s+#\s.*$/, "").trimEnd()).filter((l) => l && !l.startsWith("#")).join("\n");
    try { await navigator.clipboard.writeText(text); } catch { return; }
    button.innerHTML = DONE; button.classList.add("done");
    setTimeout(() => { button.innerHTML = COPY; button.classList.remove("done"); }, 1400);
  });
  block.append(button);
}
