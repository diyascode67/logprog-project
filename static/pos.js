(() => {
  const rupiah = new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0
  });

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => document.querySelectorAll(selector);

  const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
  })[char]);

  // Global helper for product card stepper +/-
  window.stepProductQty = (id, delta) => {
    const input = document.getElementById(`quantity-${id}`);
    if (!input) return;
    const current = parseInt(input.value, 10) || 1;
    const min = parseInt(input.min, 10) || 1;
    const max = parseInt(input.max, 10) || 9999;
    input.value = Math.min(Math.max(current + delta, min), max);
  };

  function notify(message, type = "error") {
    const alertBox = $("#pos-alert");
    if (!alertBox) return;
    alertBox.textContent = message;
    alertBox.className = `flash ${type === "error" ? "error" : "success"}`;
    alertBox.classList.remove("hidden");
    window.setTimeout(() => alertBox.classList.add("hidden"), 3600);
  }

  async function send(url, body) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Terjadi kesalahan. Coba lagi.");
    return data;
  }

  function triggerCartBadgeAnimation() {
    const badge = $("#cart-count");
    if (!badge) return;
    badge.classList.remove("apple-badge-pop");
    requestAnimationFrame(() => {
      requestAnimationFrame(() => badge.classList.add("apple-badge-pop"));
    });
  }

  // Shared state across POS sessions
  window.__posState = window.__posState || { items: [], total: 0, activeMethod: "tunai" };
  window.__posConfig = window.__posConfig || null;

  const pendingUpdates = new Map();
  async function setQuantity(id, quantity) {
    if (pendingUpdates.has(id)) {
      clearTimeout(pendingUpdates.get(id));
    }
    pendingUpdates.set(id, setTimeout(async () => {
      pendingUpdates.delete(id);
      try {
        const updateUrl = window.__posConfig?.urls?.update || "/api/pos/ubah-jumlah";
        const result = await send(updateUrl, { id_produk: id, jumlah: quantity });
        renderCart(result);
      } catch (error) {
        notify(error.message);
      }
    }, 150));
  }

  function renderCart(data) {
    window.__posState.items = data.items;
    window.__posState.total = data.total;

    const itemsContainer = $("#cart-items");
    if (itemsContainer) {
      itemsContainer.innerHTML = window.__posState.items.map((item) => `
        <div class="cart-row apple-item-anim" data-cart-id="${item.id_produk}">
          <div class="cart-row-main">
            <div class="cart-row-info">
              <p class="cart-row-title">${escapeHtml(item.nama)}</p>
              <p class="cart-row-unit">${rupiah.format(item.harga)} / item</p>
            </div>
            <p class="cart-row-subtotal">${rupiah.format(item.subtotal)}</p>
          </div>
          <div class="cart-row-bottom">
            <div class="cart-stepper">
              <button
                type="button"
                class="stepper-btn"
                data-cart-change="${item.id_produk}"
                data-delta="-1"
                aria-label="Kurangi jumlah"
              >
                <svg viewBox="0 0 24 24" fill="currentColor" width="14" height="14"><path d="M4.5 12a.75.75 0 0 1 .75-.75h13.5a.75.75 0 0 1 0 1.5H5.25A.75.75 0 0 1 4.5 12Z"/></svg>
              </button>
              <span class="stepper-val">${item.jumlah}</span>
              <button
                type="button"
                class="stepper-btn"
                data-cart-change="${item.id_produk}"
                data-delta="1"
                aria-label="Tambah jumlah"
              >
                <svg viewBox="0 0 24 24" fill="currentColor" width="14" height="14"><path d="M12 3.75a.75.75 0 0 1 .75.75v6.75h6.75a.75.75 0 0 1 0 1.5h-6.75v6.75a.75.75 0 0 1-1.5 0v-6.75H4.5a.75.75 0 0 1 0-1.5h6.75V4.5A.75.75 0 0 1 12 3.75Z"/></svg>
              </button>
            </div>
            <button
              type="button"
              class="cart-delete-btn"
              data-cart-remove="${item.id_produk}"
            >
              Hapus
            </button>
          </div>
        </div>
      `).join("");
    }

    const emptyBox = $("#cart-empty");
    if (emptyBox) emptyBox.classList.toggle("hidden", window.__posState.items.length > 0);

    const totalCount = data.jumlah_item ?? window.__posState.items.reduce((acc, cur) => acc + cur.jumlah, 0);
    const countBadge = $("#cart-count");
    if (countBadge) {
      countBadge.textContent = `${totalCount} item dipilih`;
      triggerCartBadgeAnimation();
    }

    const totalEl = $("#cart-total");
    if (totalEl) totalEl.textContent = rupiah.format(window.__posState.total);

    const paymentTotal = $("#payment-total");
    if (paymentTotal) paymentTotal.textContent = rupiah.format(window.__posState.total);

    const itemsSummary = $("#payment-items-summary");
    if (itemsSummary) {
      itemsSummary.textContent = `${window.__posState.items.length} produk (${totalCount} item)`;
    }

    const openPaymentBtn = $("#open-payment");
    if (openPaymentBtn) openPaymentBtn.disabled = window.__posState.items.length === 0;

    const btnUangPas = $("#btn-uang-pas");
    if (btnUangPas) {
      btnUangPas.textContent = `Uang Pas (${rupiah.format(window.__posState.total)})`;
    }
  }

  // Attach global document listeners once
  if (!window.__posDocumentInitialized) {
    window.__posDocumentInitialized = true;

    document.addEventListener("click", (event) => {
      const add = event.target.closest(".add-product");
      if (add) {
        const id = Number(add.dataset.id);
        const inputEl = document.getElementById(add.dataset.input);
        const amount = Number(inputEl ? inputEl.value : 1) || 1;
        const current = window.__posState.items.find((item) => item.id_produk === id)?.jumlah || 0;

        add.classList.add("apple-btn-pop");
        setTimeout(() => add.classList.remove("apple-btn-pop"), 200);

        setQuantity(id, current + amount);
        return;
      }

      const changer = event.target.closest("[data-cart-change]");
      if (changer) {
        const id = Number(changer.dataset.cartChange);
        const item = window.__posState.items.find((row) => row.id_produk === id);
        if (item) setQuantity(id, item.jumlah + Number(changer.dataset.delta));
        return;
      }

      const remover = event.target.closest("[data-cart-remove]");
      if (remover) {
        setQuantity(Number(remover.dataset.cartRemove), 0);
      }
    });

    document.addEventListener("keydown", (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        const searchInput = $("#product-search");
        if (searchInput) {
          searchInput.focus();
          searchInput.select();
        }
      }
    });
  }

  // Primary POS Initializer (callable on direct load or SPA transition)
  window.initPos = function() {
    const configElement = document.querySelector("#pos-config");
    if (!configElement) return;

    const config = JSON.parse(configElement.textContent);
    window.__posConfig = config;
    window.__posState.items = config.cart || [];
    window.__posState.total = config.total || 0;
    window.__posState.activeMethod = "tunai";

    const paymentDialog = $("#payment-dialog");
    const paymentInput = $("#uang-bayar");
    const openPayment = $("#open-payment");
    const changePreview = $("#change-preview");

    function updateChangeCalculation() {
      if (!changePreview) return;
      const paid = Number(paymentInput?.value || 0);

      if (!paid) {
        changePreview.innerHTML = `<span class="preview-placeholder">Masukkan nominal uang atau klik pilihan pecahan di atas.</span>`;
        changePreview.className = "change-preview-box";
        return;
      }

      if (paid === window.__posState.total) {
        changePreview.innerHTML = `
          <div class="change-banner exact">
            <div class="banner-text">
              <strong>Uang Pas</strong>
              <span>Tidak ada kembalian</span>
            </div>
            <span class="banner-chip chip-exact">Pas</span>
          </div>
        `;
        changePreview.className = "change-preview-box is-exact";
      } else if (paid > window.__posState.total) {
        const kembalian = paid - window.__posState.total;
        changePreview.innerHTML = `
          <div class="change-banner change">
            <div class="banner-text">
              <small>Kembalian Pelanggan</small>
              <strong class="change-num">${rupiah.format(kembalian)}</strong>
            </div>
            <span class="banner-chip chip-change">Kembalikan Uang</span>
          </div>
        `;
        changePreview.className = "change-preview-box is-change";
      } else {
        const kurang = window.__posState.total - paid;
        changePreview.innerHTML = `
          <div class="change-banner deficit">
            <div class="banner-text">
              <small>Uang Masih Kurang</small>
              <strong class="deficit-num">${rupiah.format(kurang)}</strong>
            </div>
            <span class="banner-chip chip-deficit">Belum Cukup</span>
          </div>
        `;
        changePreview.className = "change-preview-box is-deficit";
      }
    }

    // Client-side instant filter search
    const searchInput = $("#product-search");
    if (searchInput) {
      const normalizeSearch = (value) => String(value || "")
        .normalize("NFKD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLocaleLowerCase("id-ID")
        .replace(/\s+/g, " ")
        .trim();

      searchInput.addEventListener("input", () => {
        const query = normalizeSearch(searchInput.value);
        let visible = 0;
        $$("[data-product]").forEach((card) => {
          const searchable = normalizeSearch(card.dataset.search);
          const matched = !query || searchable.includes(query);
          card.classList.toggle("hidden", !matched);
          card.setAttribute("aria-hidden", String(!matched));
          if (matched) visible += 1;
        });

        const countEl = $("#product-count");
        if (countEl) countEl.textContent = visible;

        const searchEmpty = $("#search-empty");
        if (searchEmpty) searchEmpty.classList.toggle("hidden", visible !== 0);
      });
    }

    // Shortcut button
    const shortcutBtn = $("#shortcut-help");
    if (shortcutBtn && searchInput) {
      shortcutBtn.addEventListener("click", () => {
        searchInput.focus();
        searchInput.select();
      });
    }

    // Segmented Control: Switch payment methods
    const segmentButtons = $$(".payment-segmented-control .segment-btn");
    segmentButtons.forEach((btn) => {
      btn.addEventListener("click", () => {
        segmentButtons.forEach((b) => {
          b.classList.remove("active");
          b.setAttribute("aria-selected", "false");
        });
        btn.classList.add("active");
        btn.setAttribute("aria-selected", "true");

        const method = btn.dataset.method;
        window.__posState.activeMethod = method;

        $$(".payment-method-view").forEach((view) => view.classList.add("hidden"));
        const targetView = $(`#method-view-${method}`);
        if (targetView) targetView.classList.remove("hidden");

        if (method === "qris" || method === "transfer") {
          if (paymentInput) {
            paymentInput.value = window.__posState.total;
            updateChangeCalculation();
          }
        } else {
          if (paymentInput) {
            paymentInput.focus();
            updateChangeCalculation();
          }
        }
      });
    });

    // Quick cash preset chips
    const btnUangPas = $("#btn-uang-pas");
    if (btnUangPas) {
      btnUangPas.addEventListener("click", () => {
        if (paymentInput) {
          paymentInput.value = window.__posState.total;
          paymentInput.dispatchEvent(new Event("input"));
          btnUangPas.classList.add("apple-chip-active");
          setTimeout(() => btnUangPas.classList.remove("apple-chip-active"), 200);
        }
      });
    }

    $$(".cash-preset-chip[data-amount]").forEach((chip) => {
      chip.addEventListener("click", () => {
        const amount = Number(chip.dataset.amount);
        if (paymentInput) {
          paymentInput.value = amount;
          paymentInput.dispatchEvent(new Event("input"));
          chip.classList.add("apple-chip-active");
          setTimeout(() => chip.classList.remove("apple-chip-active"), 200);
        }
      });
    });

    // Open payment dialog
    if (openPayment && paymentDialog) {
      openPayment.addEventListener("click", () => {
        const paymentTotal = $("#payment-total");
        if (paymentTotal) paymentTotal.textContent = rupiah.format(window.__posState.total);

        const itemsSummary = $("#payment-items-summary");
        if (itemsSummary) {
          const totalCount = window.__posState.items.reduce((acc, cur) => acc + cur.jumlah, 0);
          itemsSummary.textContent = `${window.__posState.items.length} jenis produk (${totalCount} item)`;
        }

        segmentButtons.forEach((b, idx) => {
          b.classList.toggle("active", idx === 0);
          b.setAttribute("aria-selected", idx === 0 ? "true" : "false");
        });
        $$(".payment-method-view").forEach((v, idx) => v.classList.toggle("hidden", idx !== 0));
        window.__posState.activeMethod = "tunai";

        if (btnUangPas) {
          btnUangPas.textContent = `⚡ Uang Pas (${rupiah.format(window.__posState.total)})`;
        }

        if (paymentInput) {
          paymentInput.value = "";
        }
        updateChangeCalculation();

        paymentDialog.showModal();
        setTimeout(() => {
          if (paymentInput) paymentInput.focus();
        }, 100);
      });
    }

    if (paymentInput) {
      paymentInput.addEventListener("input", updateChangeCalculation);
    }

    // Payment Form Submit
    const paymentForm = $("#payment-form");
    if (paymentForm) {
      paymentForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const button = $("#complete-payment");
        if (button) {
          button.disabled = true;
          button.innerHTML = `<span class="apple-spinner"></span> <span>Memproses...</span>`;
        }

        const nominalBayar = Number(paymentInput?.value || window.__posState.total);

        try {
          const checkoutUrl = window.__posConfig?.urls?.checkout || "/api/pos/selesai";
          const result = await send(checkoutUrl, { uang_bayar: nominalBayar });
          if (paymentDialog) paymentDialog.close();

          renderCart({ items: [], total: 0, jumlah_item: 0 });

          const successChange = $("#success-change");
          if (successChange) {
            if (result.kembalian > 0) {
              successChange.innerHTML = `Kembalian pelanggan: <strong style="color: var(--apple-green-deep);">${rupiah.format(result.kembalian)}</strong>`;
            } else {
              successChange.innerHTML = `Pembayaran lunas (Uang Pas).`;
            }
          }

          const printReceipt = $("#print-receipt");
          if (printReceipt) {
            printReceipt.href = result.receipt_url;
            // Cukup tutup dialog — navigasi ditangani global SPA interceptor di app.js
            // agar tidak terjadi double-navigate (onclick + global listener)
            printReceipt.onclick = () => {
              if (successDialog) successDialog.close();
              // Tidak preventDefault — biarkan event bubble ke global click interceptor
            };
          }

          const successDialog = $("#success-dialog");
          if (successDialog) successDialog.showModal();
        } catch (error) {
          notify(error.message);
        } finally {
          if (button) {
            button.disabled = false;
            button.innerHTML = `<span class="btn-pay-text"><svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16"><path d="M20.03 5.97a.75.75 0 0 1 0 1.06l-10 10a.75.75 0 0 1-1.06 0l-5-5a.75.75 0 1 1 1.06-1.06L9.5 15.44l9.47-9.47a.75.75 0 0 1 1.06 0Z"/></svg> Selesaikan &amp; Buat Struk</span>`;
          }
        }
      });
    }

    // New transaction button
    const newTransactionBtn = $("#new-transaction");
    if (newTransactionBtn) {
      newTransactionBtn.addEventListener("click", () => {
        const successDialog = $("#success-dialog");
        if (successDialog) successDialog.close();
        if (searchInput) {
          searchInput.focus();
        }
      });
    }

    // Render initial cart
    renderCart({ items: window.__posState.items, total: window.__posState.total });
  };

  // Run on initial script load
  window.initPos();
})();
