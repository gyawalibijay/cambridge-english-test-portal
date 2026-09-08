/* B1_DASHBOARD_WHATSAPP_V40_2_1 */
(() => {
  "use strict";

  const WHATSAPP_URL =
    "https://wa.me/9779851319370" +
    "?text=Hello%2C%20I%20want%20to%20activate%20my%20B1%20preparation." +
    "%20Please%20send%20me%20the%20payment%20and%20access%20details.";

  const norm = (value) =>
    String(value || "")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();

  const findTitle = () => {
    const nodes = Array.from(
      document.querySelectorAll("h1,h2,h3,h4,strong,[class*='title'],[class*='copy']")
    );

    const matches = nodes.filter((node) =>
      norm(node.textContent).includes("activate your b1 preparation")
    );

    if (!matches.length) return null;

    matches.sort(
      (a, b) => norm(a.textContent).length - norm(b.textContent).length
    );
    return matches[0];
  };

  const findCard = (title) => {
    let node = title;
    let best = null;

    for (let depth = 0; node && depth < 8; depth += 1, node = node.parentElement) {
      if (!(node instanceof HTMLElement)) continue;

      const text = norm(node.textContent);
      const actions = Array.from(node.querySelectorAll("a,button"));
      const hasExpectedText =
        text.includes("payment") &&
        text.includes("activate your b1 preparation");

      const hasAction = actions.some((action) => {
        const t = norm(action.textContent);
        return (
          t === "open" ||
          t.includes("whatsapp") ||
          t.includes("payment") ||
          t.includes("activate")
        );
      });

      if (hasExpectedText && hasAction) {
        best = node;
        if (
          node.matches(
            "article,section,[class*='card'],[class*='payment'],[class*='access']"
          )
        ) {
          return node;
        }
      }
    }

    return best;
  };

  const findAction = (card) => {
    const actions = Array.from(card.querySelectorAll("a,button"));

    return (
      actions.find((el) => norm(el.textContent) === "open") ||
      actions.find((el) => norm(el.textContent).includes("whatsapp")) ||
      actions.find((el) => {
        const href = el.getAttribute("href") || "";
        return href.includes("/store") || href.includes("payment");
      }) ||
      null
    );
  };

  const makeWhatsAppLink = (oldAction) => {
    let link = oldAction;

    if (oldAction.tagName !== "A") {
      link = document.createElement("a");
      link.className = oldAction.className || "";
      oldAction.replaceWith(link);
    }

    link.href = WHATSAPP_URL;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.classList.add("b1-activation-whatsapp-v4021");
    link.setAttribute(
      "aria-label",
      "Contact Arya Academy on WhatsApp to activate B1 preparation"
    );

    link.innerHTML = `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 2a9.6 9.6 0 0 0-8.18 14.62L2.55 21.2l4.69-1.23A9.68 9.68 0 1 0 12 2Zm5.57 13.75c-.24.67-1.37 1.28-1.9 1.34-.5.05-1.15.08-1.86-.15-.43-.14-.98-.32-1.69-.63-2.97-1.28-4.91-4.27-5.06-4.47-.14-.2-1.2-1.6-1.2-3.05 0-1.45.76-2.16 1.03-2.45.27-.3.6-.37.8-.37h.57c.18 0 .43-.07.67.51.24.59.83 2.03.9 2.18.07.15.12.32.02.51-.1.2-.15.32-.3.49-.15.17-.31.37-.44.5-.15.15-.3.3-.13.59.17.3.76 1.25 1.63 2.02 1.12 1 2.06 1.31 2.35 1.46.3.15.47.12.64-.07.17-.2.74-.86.93-1.15.2-.3.4-.25.67-.15.27.1 1.72.81 2.01.96.3.15.5.22.57.34.07.12.07.7-.17 1.37Z"/>
      </svg>
      <span>WhatsApp</span>
      <span class="b1-wa-arrow-v4021" aria-hidden="true">→</span>
    `;

    return link;
  };

  const init = () => {
    const title = findTitle();
    if (!title) return;

    const card = findCard(title);
    if (!card) return;

    card.classList.add("b1-activation-card-v4021");

    const action = findAction(card);
    if (!action) return;

    makeWhatsAppLink(action);
    card.dataset.b1WhatsappReady = "1";
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
