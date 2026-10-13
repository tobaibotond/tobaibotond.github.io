// Progressive enhancement for the generated static pages (see _tools/build.py).
(function () {
  const page = document.body.dataset.page;
  const nav = document.querySelector(".nav");
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const lang = document.documentElement.lang;

  // ---------- Local preview: folder links -> index.html (servers do this themselves) ----------
  if (location.protocol === "file:") {
    document.querySelectorAll("a[href]").forEach((a) => {
      const url = new URL(a.href);
      if (url.protocol === "file:" && url.pathname.endsWith("/")) {
        url.pathname += "index.html";
        a.href = url.href;
      }
    });
  }

  // ---------- Nav: categories start closed, remember the ones opened; mobile "Index" toggle ----------
  nav.querySelectorAll("details").forEach((d) => {
    const key = "nav-cat-" + d.dataset.cat;
    try {
      if (localStorage.getItem(key) === "1") d.open = true;
    } catch (e) {}
    d.addEventListener("toggle", () => {
      try { localStorage.setItem(key, d.open ? "1" : "0"); } catch (e) {}
    });
  });

  const toggle = nav.querySelector(".nav-toggle");
  toggle.addEventListener("click", () => {
    const open = !nav.classList.contains("open");
    nav.classList.toggle("open", open);
    toggle.setAttribute("aria-expanded", String(open));
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && nav.classList.contains("open")) toggle.click();
  });

  if (page === "home") initHome();
  if (page === "project") initProject();

  // ---------- Home ----------
  function initHome() {
    const home = document.querySelector(".home");
    const tiles = [...home.querySelectorAll("a[data-slug]")];
    const navLinks = [...nav.querySelectorAll("li a[data-slug]")];

    // Nav hover highlights that project's tiles
    const setHighlight = (slug) => {
      home.classList.toggle("dim", !!slug);
      tiles.forEach((t) => t.classList.toggle("hl", t.dataset.slug === slug));
      navLinks.forEach((a) => a.classList.toggle("is-hover", a.dataset.slug === slug));
    };
    navLinks.forEach((a) => {
      a.addEventListener("mouseenter", () => setHighlight(a.dataset.slug));
      a.addEventListener("mouseleave", () => setHighlight(null));
      a.addEventListener("focus", () => setHighlight(a.dataset.slug));
      a.addEventListener("blur", () => setHighlight(null));
    });

    // Label follows the cursor over tiles
    const label = document.createElement("div");
    label.className = "cursor-label";
    label.setAttribute("aria-hidden", "true");
    document.body.appendChild(label);
    home.addEventListener("mousemove", (e) => {
      const t = e.target.closest("a[data-label]");
      if (!t) return label.classList.remove("on");
      label.textContent = t.dataset.label;
      label.style.left = e.clientX + "px";
      label.style.top = e.clientY + "px";
      label.classList.add("on");
    });
    home.addEventListener("mouseleave", () => label.classList.remove("on"));

    // Film strips open in the lightbox
    setupLightbox([...home.querySelectorAll(".grid .zoom")]);

    // Moving covers play only while visible (and never with reduced motion)
    const videos = home.querySelectorAll("video");
    if (reduceMotion || !videos.length || !("IntersectionObserver" in window)) return;
    const io = new IntersectionObserver((entries) => {
      entries.forEach(({ target, isIntersecting }) => {
        if (isIntersecting) target.play().catch(() => {});
        else target.pause();
      });
    }, { rootMargin: "100px" });
    videos.forEach((v) => io.observe(v));
  }

  // ---------- Project ----------
  function initProject() {
    // Video facade: load the player only when asked
    const box = document.querySelector(".video[data-src]");
    if (box) {
      box.querySelector(".video-play").addEventListener("click", () => {
        let el;
        if (box.dataset.kind === "file") {
          el = document.createElement("video");
          el.src = box.dataset.src;
          el.controls = true;
          el.autoplay = true;
          el.playsInline = true;
        } else {
          el = document.createElement("iframe");
          el.src = box.dataset.src;
          el.allow = "autoplay; fullscreen; picture-in-picture";
          el.allowFullscreen = true;
        }
        el.title = box.dataset.title;
        box.replaceChildren(el);
        el.focus();
      });
    }

    setupLightbox([...document.querySelectorAll(".stack .zoom")]);

    // Jump to an image when linked as #n
    if (location.hash) {
      const target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
      if (target) target.scrollIntoView({ block: "start" });
    }
  }

  // ---------- Lightbox (accessible dialog) ----------
  function setupLightbox(buttons) {
    if (!buttons.length) return;
    const t = lang === "hu"
      ? { dialog: "Kép nagyítva", close: "Bezárás", prev: "Előző kép", next: "Következő kép" }
      : { dialog: "Enlarged image", close: "Close", prev: "Previous image", next: "Next image" };

    const lb = document.createElement("div");
    lb.className = "lightbox";
    lb.setAttribute("role", "dialog");
    lb.setAttribute("aria-modal", "true");
    lb.setAttribute("aria-label", t.dialog);
    lb.innerHTML =
      `<button type="button" class="close" aria-label="${t.close}">✕</button>` +
      `<span class="count" aria-live="polite"></span>` +
      `<button type="button" class="prev" aria-label="${t.prev}">←</button>` +
      `<img alt="">` +
      `<button type="button" class="next" aria-label="${t.next}">→</button>`;
    document.body.appendChild(lb);

    const img = lb.querySelector("img");
    const count = lb.querySelector(".count");
    const focusables = [...lb.querySelectorAll("button")];
    let i = 0;
    let opener = null;

    const show = (n) => {
      i = (n + buttons.length) % buttons.length;
      const b = buttons[i];
      const thumb = b.querySelector("img");
      // Very tall images (film strips) get a scrollable, readable-width view
      lb.classList.toggle("tall", thumb.getAttribute("height") / thumb.getAttribute("width") > 2);
      lb.scrollTop = 0;
      img.src = b.dataset.full;
      img.alt = thumb.alt;
      count.textContent = `${i + 1} / ${buttons.length}`;
    };
    const open = (n) => {
      opener = buttons[n];
      show(n);
      lb.classList.add("open");
      document.body.style.overflow = "hidden";
      lb.querySelector(".close").focus();
    };
    const close = () => {
      lb.classList.remove("open");
      document.body.style.overflow = "";
      if (opener) opener.focus();
    };

    buttons.forEach((b, n) => b.addEventListener("click", () => open(n)));
    lb.querySelector(".prev").addEventListener("click", (e) => { e.stopPropagation(); show(i - 1); });
    lb.querySelector(".next").addEventListener("click", (e) => { e.stopPropagation(); show(i + 1); });
    lb.querySelector(".close").addEventListener("click", (e) => { e.stopPropagation(); close(); });
    lb.addEventListener("click", close);

    document.addEventListener("keydown", (e) => {
      if (!lb.classList.contains("open")) return;
      if (e.key === "Escape") close();
      else if (e.key === "ArrowLeft") show(i - 1);
      else if (e.key === "ArrowRight") show(i + 1);
      else if (e.key === "Tab") {
        // Keep focus inside the dialog
        const k = focusables.indexOf(document.activeElement);
        const next = (k + (e.shiftKey ? -1 : 1) + focusables.length) % focusables.length;
        focusables[next].focus();
        e.preventDefault();
      }
    });

    // Swipe on touch screens
    let x0 = null;
    lb.addEventListener("touchstart", (e) => (x0 = e.touches[0].clientX), { passive: true });
    lb.addEventListener("touchend", (e) => {
      if (x0 === null) return;
      const dx = e.changedTouches[0].clientX - x0;
      if (Math.abs(dx) > 40) {
        show(dx < 0 ? i + 1 : i - 1);
        e.preventDefault(); // don't treat the swipe as a click that closes
      }
      x0 = null;
    });
  }
})();
