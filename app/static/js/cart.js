
(function(){
  var btn = document.getElementById("btn-use-location");
  var status = document.getElementById("loc-status");
  var latEl = document.getElementById("customer-lat");
  var lngEl = document.getElementById("customer-lng");
  function setLoc(lat, lng) {
    if (latEl) latEl.value = lat;
    if (lngEl) lngEl.value = lng;
    if (status) status.textContent = "Location shared ✓";
    fetchEstimate(lat, lng);
  }
  function fetchEstimate(lat, lng) {
    var box = document.getElementById("delivery-estimate");
    var feeEl = document.getElementById("delivery-fee-paisa");
    fetch("/api/delivery/estimate?lat=" + encodeURIComponent(lat) + "&lng=" + encodeURIComponent(lng))
      .then(function(r){ return r.json().then(function(d){ return {ok:r.ok, d:d}; }); })
      .then(function(res){
        var d = res.d;
        if (box) box.style.display = "block";
        var dist = document.getElementById("est-distance");
        var fee = document.getElementById("est-fee");
        var eta = document.getElementById("est-eta");
        var msg = document.getElementById("est-msg");
        if (d.distance_km != null && dist) dist.textContent = d.distance_km + " km";
        else if (dist) dist.textContent = "—";
        if (fee) fee.textContent = d.delivery_fee_npr != null ? ("Rs. " + d.delivery_fee_npr) : "—";
        if (feeEl && d.delivery_fee_paisa != null) feeEl.value = d.delivery_fee_paisa;
        if (eta) eta.textContent = d.eta_minutes != null ? (d.eta_minutes + " min") : "—";
        if (msg) {
          if (!d.allowed) { msg.style.display = "block"; msg.textContent = d.message || "Outside delivery area"; }
          else { msg.style.display = "none"; msg.textContent = ""; }
        }
        window.__deliveryAllowed = d.allowed !== false;
      })
      .catch(function(){});
  }
  function askLoc() {
    if (!navigator.geolocation) {
      if (status) status.textContent = "Location not supported on this device.";
      return;
    }
    if (status) status.textContent = "Getting location…";
    navigator.geolocation.getCurrentPosition(
      function(pos){ setLoc(pos.coords.latitude, pos.coords.longitude); },
      function(err){ if (status) status.textContent = "Please allow location access."; },
      { enableHighAccuracy: true, timeout: 15000 }
    );
  }
  if (btn) btn.addEventListener("click", askLoc);
  // Auto-ask when delivery selected
  document.querySelectorAll('input[name="order_type"]').forEach(function(r){
    r.addEventListener("change", function(){
      if (r.value === "delivery" && r.checked) askLoc();
    });
  });
})();


  var delOpt = document.getElementById("opt-delivery");
  var delFields = document.getElementById("delivery-fields");
  function syncDelivery() {
    var checked = document.querySelector('input[name="order_type"]:checked');
    if (delFields) delFields.style.display = (checked && checked.value === "delivery") ? "block" : "none";
  }
  document.querySelectorAll('input[name="order_type"]').forEach(function(r){
    r.addEventListener("change", syncDelivery);
  });
  syncDelivery();

/* Cart page & order submission */
(function () {
  "use strict";

  function formatPrice(paisa) {
    var npr = paisa / 100;
    return "Rs. " + (npr % 1 === 0 ? npr : npr.toFixed(2));
  }

  function renderCart() {
    var container = document.getElementById("cart-items");
    var summary = document.getElementById("cart-summary");
    if (!container) return;

    var cart = window.MeghaCart.get();
    if (!cart.length) {
      container.innerHTML =
        '<div class="empty-state"><h3>Your cart is empty</h3><p><a href="/menu" class="btn btn-primary">Browse Menu</a></p></div>';
      if (summary) summary.style.display = "none";
      return;
    }

    container.innerHTML = cart
      .map(function (item) {
        return (
          '<div class="cart-item" data-key="' +
          item._key +
          '">' +
          "<div><strong>" +
          item.item_name +
          "</strong>" +
          (item.variant_name ? "<br><small>" + item.variant_name + "</small>" : "") +
          (item.special_instructions
            ? "<br><small>Note: " + item.special_instructions + "</small>"
            : "") +
          '<div class="qty-control" style="margin-top:0.5rem">' +
          '<button type="button" data-qty-minus="' +
          item._key +
          '">−</button>' +
          "<span>" +
          item.quantity +
          "</span>" +
          '<button type="button" data-qty-plus="' +
          item._key +
          '">+</button></div></div>' +
          '<div style="text-align:right">' +
          '<div class="price">' +
          formatPrice(
            (item.unit_price_paisa + (item.addons_total || 0)) * item.quantity
          ) +
          "</div>" +
          '<button type="button" class="btn btn-sm" data-remove="' +
          item._key +
          '" style="margin-top:0.35rem;color:#9B2226">Remove</button></div></div>'
        );
      })
      .join("");

    var total = window.MeghaCart.total();
    if (summary) {
      summary.style.display = "block";
      var sub = summary.querySelector("[data-subtotal]");
      var tot = summary.querySelector("[data-total]");
      if (sub) sub.textContent = formatPrice(total);
      if (tot) tot.textContent = formatPrice(total);
    }

    container.querySelectorAll("[data-qty-minus]").forEach(function (b) {
      b.addEventListener("click", function () {
        var key = b.getAttribute("data-qty-minus");
        var item = window.MeghaCart.get().find(function (c) {
          return c._key === key;
        });
        if (item && item.quantity > 1) {
          window.MeghaCart.updateQty(key, item.quantity - 1);
          renderCart();
        }
      });
    });
    container.querySelectorAll("[data-qty-plus]").forEach(function (b) {
      b.addEventListener("click", function () {
        var key = b.getAttribute("data-qty-plus");
        var item = window.MeghaCart.get().find(function (c) {
          return c._key === key;
        });
        if (item) {
          window.MeghaCart.updateQty(key, item.quantity + 1);
          renderCart();
        }
      });
    });
    container.querySelectorAll("[data-remove]").forEach(function (b) {
      b.addEventListener("click", function () {
        window.MeghaCart.remove(b.getAttribute("data-remove"));
        renderCart();
      });
    });
  }

  function uuid() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return "id-" + Date.now() + "-" + Math.random().toString(16).slice(2);
  }

  async function submitOrder(e) {
    e.preventDefault();
    var btn = document.getElementById("submit-order-btn");
    var errBox = document.getElementById("order-error");
    if (errBox) {
      errBox.style.display = "none";
      errBox.textContent = "";
    }
    var cart = window.MeghaCart.get();
    if (!cart.length) return;

    var tableToken = (document.getElementById("table-token") || {}).value || "";
    var orderType = tableToken
      ? "dine_in"
      : (document.querySelector("[name=order_type]:checked") || {}).value ||
        "takeaway";
    var special = (document.getElementById("special-instructions") || {}).value || "";
    var name = (document.getElementById("customer-name") || {}).value || "";
    var phone = (document.getElementById("customer-phone") || {}).value || "";
    var email = (document.getElementById("customer-email") || {}).value || "";
    var ot = document.querySelector('input[name="order_type"]:checked');
    if (ot && ot.value === "delivery") {
      var clat = (document.getElementById("customer-lat") || {}).value;
      var clng = (document.getElementById("customer-lng") || {}).value;
      if (!clat || !clng) {
        if (errBox) { errBox.textContent = "Please share your location for delivery."; errBox.style.display = "block"; }
        else alert("Please share your location for delivery.");
        return;
      }
      if (window.__deliveryAllowed === false) {
        if (errBox) { errBox.textContent = "Sorry, your location is outside our delivery area."; errBox.style.display = "block"; }
        else alert("Outside delivery area.");
        return;
      }
      var addr = (document.getElementById("delivery-address") || {}).value || "";
      if (!addr.trim()) {
        if (errBox) { errBox.textContent = "Delivery address is required."; errBox.style.display = "block"; }
        else alert("Delivery address is required.");
        return;
      }
    }
    if (!email || email.indexOf("@") < 0) {
      if (errBox) { errBox.textContent = "Email is required."; errBox.style.display = "block"; }
      else alert("Email is required.");
      return;
    }

    var items = cart.map(function (c) {
      return {
        menu_item_id: c.menu_item_id,
        variant_id: c.variant_id || null,
        quantity: c.quantity,
        addon_ids: c.addon_ids || [],
        special_instructions: c.special_instructions || null,
      };
    });

    btn.disabled = true;
    btn.textContent = "Placing order…";

    try {
      var res = await fetch("/orders/submit", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Idempotency-Key": uuid(),
        },
        body: JSON.stringify({
          items: items,
          order_type: orderType,
          table_token: tableToken || null,
          special_instructions: special,
          customer_name: name || null,
          customer_phone: phone || null,
          customer_email: email,
          delivery_address: (document.getElementById("delivery-address") || {}).value || null,
          delivery_notes: (document.getElementById("delivery-notes") || {}).value || null,
          delivery_fee_paisa: parseInt((document.getElementById("delivery-fee-paisa")||{}).value||"0",10)||0,
          customer_lat: (document.getElementById("customer-lat") || {}).value || null,
          customer_lng: (document.getElementById("customer-lng") || {}).value || null,
        }),
      });
      var data = await res.json().catch(function () {
        return {};
      });
      if (!res.ok) {
        throw new Error(data.error || "Order failed (" + res.status + ")");
      }
      window.MeghaCart.clear();
      window.location.href = data.tracking_url;
    } catch (err) {
      if (errBox) {
        errBox.textContent = err.message || "Could not place order. Please try again.";
        errBox.style.display = "block";
      } else {
        alert(err.message || "Could not place order. Please try again.");
      }
      btn.disabled = false;
      btn.textContent = "Place Order";
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    renderCart();
    var form = document.getElementById("order-form");
    if (form) form.addEventListener("submit", submitOrder);
  });
})();
