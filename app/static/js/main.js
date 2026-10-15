/* Megha Hotel – Public JS */
(function () {
  "use strict";

  // Mobile nav
  const toggle = document.querySelector(".nav-toggle");
  const links = document.querySelector(".nav-links");
  if (toggle && links) {
    toggle.addEventListener("click", () => links.classList.toggle("open"));
  }

  // Cart (localStorage)
  const CART_KEY = "megha_cart";

  function getCart() {
    try {
      return JSON.parse(localStorage.getItem(CART_KEY) || "[]");
    } catch {
      return [];
    }
  }

  function saveCart(cart) {
    localStorage.setItem(CART_KEY, JSON.stringify(cart));
    updateCartBadge();
  }

  function updateCartBadge() {
    const cart = getCart();
    const count = cart.reduce((s, i) => s + (i.quantity || 1), 0);
    document.querySelectorAll("[data-cart-count]").forEach((el) => {
      el.textContent = count;
      el.style.display = count > 0 ? "inline-flex" : "none";
    });
  }

  window.MeghaCart = {
    get: getCart,
    save: saveCart,
    add(item) {
      const cart = getCart();
      const key = `${item.menu_item_id}-${item.variant_id || 0}-${(item.addon_ids || []).join(",")}`;
      const existing = cart.find((c) => c._key === key);
      if (existing) {
        existing.quantity += item.quantity || 1;
      } else {
        cart.push({ ...item, _key: key, quantity: item.quantity || 1 });
      }
      saveCart(cart);
      return cart;
    },
    remove(key) {
      saveCart(getCart().filter((c) => c._key !== key));
    },
    updateQty(key, qty) {
      const cart = getCart();
      const item = cart.find((c) => c._key === key);
      if (item) {
        item.quantity = Math.max(1, qty);
        saveCart(cart);
      }
    },
    clear() {
      saveCart([]);
    },
    total() {
      return getCart().reduce((s, i) => s + (i.unit_price_paisa + (i.addons_total || 0)) * i.quantity, 0);
    },
  };

  updateCartBadge();

  // Add to cart buttons
  document.querySelectorAll("[data-add-to-cart]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = parseInt(btn.dataset.itemId, 10);
      const name = btn.dataset.itemName;
      const price = parseInt(btn.dataset.itemPrice, 10);
      window.MeghaCart.add({
        menu_item_id: id,
        item_name: name,
        unit_price_paisa: price,
        quantity: 1,
        addon_ids: [],
        addons_total: 0,
      });
      btn.textContent = "Added ✓";
      setTimeout(() => { btn.textContent = "Add to Cart"; }, 1200);
    });
  });
})();
