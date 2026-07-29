'use strict';

/* ═══════════════════════════════════════════════════════════════════════════
   Instamart — Try Next Basket  |  shop.js v2.0
   Swiggy Instamart clone frontend with ENG-006 AI recommendation integration
   ═══════════════════════════════════════════════════════════════════════════ */

const Shop = {
  /** @type {Array<Object>} All products from /api/products */
  products: [],

  /** @type {Object<number, number>} product_id → quantity */
  cart: {},

  /** @type {string|null} Toast timer ID */
  _toastTimer: null,

  // ─── Search placeholders that cycle like the real Instamart ────────────────
  _searchPlaceholders: [
    'Search for "Rice"',
    'Search for "Atta"',
    'Search for "Chips"',
    'Search for "Milk"',
    'Search for "Dal"',
  ],
  _placeholderIdx: 0,
  _placeholderTimer: null,

  /* ════════════════════════════════════════════════════════════════════════
     BOOT
     ════════════════════════════════════════════════════════════════════════ */
  async init() {
    await this._loadUsers();  // calls _loadCart() internally
    await this._loadProducts();
    this._bindSearch();
    this._bindUserSelect();
    this._startPlaceholderCycle();
  },

  /* ════════════════════════════════════════════════════════════════════════
     PRODUCTS — load and render grouped by category
     ════════════════════════════════════════════════════════════════════════ */
  async _loadProducts() {
    try {
      const data = await fetch('/api/products').then(r => r.json());
      this.products = data.products || [];
      this._hideSkeleton();
      this._renderCategoryShelves();
    } catch (e) {
      console.error('Product load failed:', e);
      this._hideSkeleton();
      const wrap = document.getElementById('categoryShelves');
      if (wrap) {
        wrap.innerHTML = `
          <div style="padding:40px;text-align:center;color:var(--text-muted)">
            <p style="font-size:15px;font-weight:600;margin-bottom:8px">Could not load products</p>
            <p style="font-size:13px">Make sure the API server is running on port 8080</p>
            <button onclick="location.reload()" style="margin-top:16px;padding:8px 20px;background:var(--orange);color:#fff;border:none;border-radius:var(--r-pill);font-size:13px;font-weight:600;cursor:pointer">Retry</button>
          </div>`;
      }
    }
  },

  _hideSkeleton() {
    const loader = document.getElementById('shelvesLoader');
    if (loader) loader.hidden = true;
  },

  /**
   * Group products by category_name and render one shelf per category.
   * Category order is determined by first-seen order in the products array.
   */
  _renderCategoryShelves() {
    const wrap = document.getElementById('categoryShelves');
    if (!wrap) return;

    // Group products by category
    const groups = new Map();
    for (const p of this.products) {
      const cat = p.category_name || 'Other';
      if (!groups.has(cat)) groups.set(cat, []);
      groups.get(cat).push(p);
    }

    wrap.innerHTML = '';
    for (const [category, items] of groups) {
      const section = document.createElement('section');
      section.className = 'category-shelf';
      section.setAttribute('aria-label', category);

      const heading = document.createElement('h2');
      heading.className = 'shelf-heading';
      heading.textContent = category;

      const row = document.createElement('div');
      row.className = 'shelf-row';
      row.id = `shelf-${this._slugify(category)}`;

      for (const p of items) {
        row.insertAdjacentHTML('beforeend', this._productTileHTML(p));
      }

      section.appendChild(heading);
      section.appendChild(row);
      wrap.appendChild(section);
    }
  },

  /** Render a single product tile (used both for first render and cart updates) */
  _productTileHTML(p) {
    const qty   = this.cart[p.id] || 0;
    const inCart = qty > 0;
    const imgEl = p.image_url
      ? `<img src="${p.image_url}" alt="${this._esc(p.name)}" loading="lazy" onerror="this.parentElement.innerHTML='${this._categoryEmoji(p.category_name)}';">`
      : this._categoryEmoji(p.category_name);

    return `
      <div class="product-tile" data-product-id="${p.id}" id="tile-${p.id}">
        <div class="product-tile-img">${imgEl}</div>
        <div class="product-tile-name" title="${this._esc(p.name)}">${this._esc(p.name)}</div>
        <div class="product-tile-price">₹${Number(p.price).toFixed(0)}</div>
        <button
          class="btn-add-tile ${inCart ? 'state-in-cart' : 'state-add'}"
          id="add-btn-${p.id}"
          onclick="Shop.toggleProduct(${p.id})"
          aria-label="${inCart ? 'Remove ' + this._esc(p.name) + ' from cart' : 'Add ' + this._esc(p.name) + ' to cart'}"
        >
          ${inCart ? `✓ In Cart (${qty})` : '+ Add'}
        </button>
      </div>`;
  },

  /** Re-render only a single tile in place (avoids full DOM rewrite) */
  _refreshTile(productId) {
    const tile = document.getElementById(`tile-${productId}`);
    if (!tile) return;
    const p = this.products.find(x => x.id === productId);
    if (!p) return;
    tile.outerHTML = this._productTileHTML(p);
  },

  /* ════════════════════════════════════════════════════════════════════════
     SEARCH — client-side filter
     ════════════════════════════════════════════════════════════════════════ */
  _bindSearch() {
    const input = document.getElementById('searchInput');
    if (!input) return;
    input.addEventListener('input', () => {
      const q = input.value.trim().toLowerCase();
      this._filterShelves(q);
    });
  },

  _filterShelves(query) {
    const shelves = document.querySelectorAll('.category-shelf');
    for (const shelf of shelves) {
      const tiles = shelf.querySelectorAll('.product-tile');
      let visibleCount = 0;
      for (const tile of tiles) {
        const pid = Number(tile.dataset.productId);
        const p = this.products.find(x => x.id === pid);
        const match = !query
          || (p && p.name.toLowerCase().includes(query))
          || (p && p.category_name.toLowerCase().includes(query));
        tile.style.display = match ? '' : 'none';
        if (match) visibleCount++;
      }
      // Hide entire shelf if nothing matches
      shelf.style.display = visibleCount === 0 ? 'none' : '';
    }
  },

  _startPlaceholderCycle() {
    const input = document.getElementById('searchInput');
    if (!input) return;
    this._placeholderTimer = setInterval(() => {
      this._placeholderIdx = (this._placeholderIdx + 1) % this._searchPlaceholders.length;
      input.placeholder = this._searchPlaceholders[this._placeholderIdx];
    }, 2200);
  },

  /* ════════════════════════════════════════════════════════════════════════
     CURRENT USER
     ════════════════════════════════════════════════════════════════════════ */
  _userId() {
    const val = document.getElementById('userSelect')?.value;
    return val ? Number(val) : 1;
  },

  async _loadUsers() {
    try {
      const data = await fetch('/api/users').then(r => r.json());
      const sel = document.getElementById('userSelect');
      if (!sel || !data.users) return;
      sel.innerHTML = '';
      for (const u of data.users) {
        const opt = document.createElement('option');
        opt.value = u.id;
        opt.textContent = u.name;
        sel.appendChild(opt);
      }
    } catch (e) {
      console.error('User load failed:', e);
    }
  },

  _bindUserSelect() {
    const sel = document.getElementById('userSelect');
    if (!sel) return;
    sel.addEventListener('change', () => this._onUserChange());
  },

  async _onUserChange() {
    this.cart = {};
    this._updateCartUI();
    const sidebar = document.getElementById('cartSidebar');
    if (sidebar) sidebar.classList.remove('open');
    await this._loadCart();
  },

  /* ════════════════════════════════════════════════════════════════════════
     CART — load from DB
     ════════════════════════════════════════════════════════════════════════ */
  async _loadCart() {
    try {
      const uid = this._userId();
      const data = await fetch(`/api/cart?user_id=${uid}`).then(r => r.json());
      this.cart = {};
      if (data.items && Array.isArray(data.items)) {
        for (const item of data.items) {
          this.cart[item.product_id] = item.quantity;
        }
      }
      this._updateCartUI();
      // Refresh all product tiles to show correct button states
      for (const p of this.products) {
        this._refreshTile(p.id);
      }
    } catch (e) {
      console.error('Cart load failed:', e);
    }
  },

  async _syncCartToDb(productId, quantity) {
    const uid = this._userId();
    try {
      const res = await fetch('/api/cart', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: uid, product_id: productId, quantity }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        throw new Error(data.error || `Server returned ${res.status}`);
      }
    } catch (e) {
      console.error('Cart sync failed:', e);
      this._toast(`Cart sync error: ${e.message}`, 'error');
    }
  },

  /* ════════════════════════════════════════════════════════════════════════
     CART — toggle product, update UI
     ════════════════════════════════════════════════════════════════════════ */
  async toggleProduct(productId) {
    const wasEmpty = this._cartCount() === 0;
    const alreadyInCart = !!this.cart[productId];
    const newQty = alreadyInCart ? 0 : 1;

    // Optimistic local update
    if (alreadyInCart) {
      delete this.cart[productId];
    } else {
      this.cart[productId] = 1;
    }
    this._refreshTile(productId);
    this._updateCartUI();

    // Sync to DB
    await this._syncCartToDb(productId, newQty);

    // Revert on failure — reload from DB to get canonical state
    if (this._cartCount() === 0) {
      // Cart empty: nothing to recommend
    } else if (wasEmpty) {
      this.openCart();
    }

    // Refresh flash recommendations for all cart items
    this._renderFlashRecs();

    // Animate badge
    this._bumpBadge();
  },

  async changeQty(productId, delta) {
    const cur = this.cart[productId] || 0;
    const next = cur + delta;

    // Optimistic local update
    if (next <= 0) {
      delete this.cart[productId];
    } else {
      this.cart[productId] = next;
    }
    this._refreshTile(productId);
    this._updateCartUI();

    // Sync to DB
    await this._syncCartToDb(productId, Math.max(next, 0));

    if (this._cartCount() > 0) {
      this._renderFlashRecs();
    }
  },

  _cartCount() {
    return Object.values(this.cart).reduce((s, q) => s + q, 0);
  },

  _updateCartUI() {
    // Badge
    const count = this._cartCount();
    const badge = document.getElementById('cartBadge');
    if (badge) badge.textContent = count;

    const empty   = document.getElementById('cartEmpty');
    const items   = document.getElementById('cartItems');
    const footer  = document.getElementById('cartFooter');

    if (count === 0) {
      if (empty)  empty.style.display = 'flex';
      if (items)  items.innerHTML = '';
      if (footer) footer.style.display = 'none';
      return;
    }

    if (empty)  empty.style.display = 'none';
    if (footer) footer.style.display = 'block';

    // Build item list HTML
    let total = 0;
    const itemsHTML = Object.entries(this.cart).map(([id, qty]) => {
      const p = this.products.find(x => x.id === Number(id));
      if (!p) return '';
      total += Number(p.price) * qty;
      const imgEl = p.image_url
        ? `<img src="${p.image_url}" alt="${this._esc(p.name)}" onerror="this.parentElement.innerHTML='${this._categoryEmoji(p.category_name)}';">`
        : this._categoryEmoji(p.category_name);
      return `
        <div class="cart-item" data-cart-id="${p.id}">
          <div class="cart-item-img">${imgEl}</div>
          <div class="cart-item-info">
            <div class="cart-item-name">${this._esc(p.name)}</div>
            <div class="cart-item-cat">${this._esc(p.category_name)}</div>
            <div class="cart-item-row">
              <span class="cart-item-price">₹${(Number(p.price) * qty).toFixed(0)}</span>
              <div class="qty-controls" role="group" aria-label="Quantity for ${this._esc(p.name)}">
                <button class="qty-btn" onclick="Shop.changeQty(${p.id}, -1)" aria-label="Decrease quantity">−</button>
                <span class="qty-val" aria-label="${qty} items">${qty}</span>
                <button class="qty-btn" onclick="Shop.changeQty(${p.id}, 1)" aria-label="Increase quantity">+</button>
              </div>
            </div>
          </div>
        </div>
        <div class="flash-rec" id="flash-${p.id}"></div>`;
    }).join('');

    if (items) items.innerHTML = itemsHTML;

    const totalEl = document.getElementById('cartTotal');
    if (totalEl) totalEl.textContent = `₹${total.toFixed(0)}`;
  },

  /* ════════════════════════════════════════════════════════════════════════
     CART OPEN / CLOSE
     ════════════════════════════════════════════════════════════════════════ */
  async openCart() {
    const sidebar  = document.getElementById('cartSidebar');
    const overlay  = document.getElementById('cartOverlay');
    if (!sidebar) return;

    sidebar.classList.add('open');
    if (overlay) overlay.classList.add('open');

    // Trap focus inside sidebar for accessibility
    sidebar.focus && sidebar.focus();

    // Refresh cart from DB
    await this._loadCart();

    // Render flash recommendations for all cart items
    if (this._cartCount() > 0) {
      this._renderFlashRecs();
    }
  },

  closeCart() {
    const sidebar = document.getElementById('cartSidebar');
    const overlay = document.getElementById('cartOverlay');
    if (sidebar) sidebar.classList.remove('open');
    if (overlay) overlay.classList.remove('open');
  },

  /* ════════════════════════════════════════════════════════════════════════
     FLASH RECOMMENDATIONS — calls ENG-006 /api/recommend, renders inline
     ════════════════════════════════════════════════════════════════════════ */
  async _renderFlashRecs() {
    if (this._cartCount() === 0) return;

    const cartItems = Object.entries(this.cart).map(([product_id, quantity]) => ({
      product_id: Number(product_id),
      quantity,
    }));
    const userId = Number(document.getElementById('userSelect')?.value || 1);

    // Show loading placeholders
    Object.keys(this.cart).forEach(pid => {
      const el = document.getElementById(`flash-${pid}`);
      if (el) el.innerHTML = `<div class="flash-thinking">⚡ thinking…</div>`;
    });

    try {
      const res = await fetch('/api/recommend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, cart_items: cartItems }),
      });
      const data = await res.json();
      if (!res.ok || data.error) throw new Error(data.error || 'Error');

      const recs = data.recommendations || [];
      recs.forEach(entry => {
        const cp = entry.cart_product;
        const rec = entry.flash_recommendation;
        if (!cp || !rec) return;

        const el = document.getElementById(`flash-${cp.id}`);
        if (!el) return;

        const imgEl = rec.image_url
          ? `<img src="${rec.image_url}" alt="${this._esc(rec.name)}" loading="lazy" onerror="this.parentElement.innerHTML='📦';">`
          : '📦';

        el.innerHTML = `
          <div class="flash-card">
            <div class="flash-icon">⚡</div>
            <div class="flash-body">
              <div class="flash-label">Pairs well with</div>
              <div class="flash-name">${this._esc(rec.name)}</div>
              <div class="flash-price">₹${Number(rec.price).toFixed(0)}</div>
              <div class="flash-rationale">${this._esc(entry.rationale || '')}</div>
            </div>
            <button class="flash-add-btn" onclick="Shop.feedback(${rec.id}, 'add_to_cart')">+ Add</button>
          </div>`;
      });
    } catch (e) {
      console.error('Flash recs failed:', e);
    }
  },

  /* ════════════════════════════════════════════════════════════════════════
     FEEDBACK — logs Add to Cart / Not Interested to PostgreSQL via /api/feedback
     ════════════════════════════════════════════════════════════════════════ */
  async feedback(productId, action) {
    const userId = Number(document.getElementById('userSelect')?.value || 1);

    // Immediately disable buttons to prevent double-submit
    const addBtn  = document.getElementById(`rec-add-${productId}`);
    const skipBtn = document.getElementById(`rec-skip-${productId}`);
    if (addBtn)  addBtn.disabled  = true;
    if (skipBtn) skipBtn.disabled = true;

    try {
      const res = await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, product_id: productId, action }),
      });

      const data = await res.json();

      if (!res.ok || !data.ok) {
        throw new Error(data.error || `Server returned ${res.status}`);
      }

      if (action === 'add_to_cart') {
        // Add the recommended product to the main cart
        this.cart[productId] = (this.cart[productId] || 0) + 1;
        this._refreshTile(productId);
        // Persist to DB immediately so it doesn't disappear on next _loadCart
        await this._syncCartToDb(productId, this.cart[productId]);
        this._updateCartUI();
        this._bumpBadge();
        this._toast('Added to cart! 🛒', 'success');
        this._renderFlashRecs();

        // Update button state
        if (addBtn) {
          addBtn.textContent = '✓ Added';
          addBtn.style.background = 'var(--text-ghost)';
        }
      } else {
        // Not interested — fade the card out
        this._toast('Got it, skipped! 👍', 'success');
        const card = document.getElementById(`rec-card-${productId}`);
        if (card) {
          card.style.transition = 'opacity 0.4s, transform 0.4s';
          card.style.opacity = '0.35';
          card.style.transform = 'scale(0.97)';
          card.setAttribute('aria-hidden', 'true');
        }
      }
    } catch (e) {
      console.error('Feedback failed:', e);
      this._toast(`Feedback failed: ${e.message}`, 'error');
      // Re-enable buttons on error
      if (addBtn)  addBtn.disabled  = false;
      if (skipBtn) skipBtn.disabled = false;
    }
  },

  /* ════════════════════════════════════════════════════════════════════════
     HELPERS
     ════════════════════════════════════════════════════════════════════════ */
  _esc(s) {
    if (!s) return '';
    return String(s)
      .replace(/&/g,  '&amp;')
      .replace(/</g,  '&lt;')
      .replace(/>/g,  '&gt;')
      .replace(/"/g,  '&quot;')
      .replace(/'/g,  '&#x27;');
  },

  _slugify(s) {
    return String(s).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  },

  /** Map category name to a contextually relevant emoji */
  _categoryEmoji(cat) {
    const map = {
      'vegetables': '🥦', 'fruits': '🍎', 'dairy': '🥛', 'eggs': '🥚',
      'meat': '🍗', 'seafood': '🐟', 'snacks': '🍿', 'drinks': '🥤',
      'beverages': '☕', 'ice cream': '🍨', 'chocolate': '🍫', 'biscuits': '🍪',
      'grocery': '🛒', 'masala': '🌶️', 'spices': '🌿', 'oil': '🫙',
      'ghee': '🫙', 'rice': '🍚', 'dal': '🍲', 'atta': '🌾',
      'cleaning': '🧹', 'personal care': '🧴', 'beauty': '💄',
      'health': '💊', 'baby': '👶', 'pet': '🐾', 'electronics': '📱',
      'kitchen': '🍳', 'home': '🏠', 'fashion': '👕', 'sports': '🏋️',
    };
    const lower = (cat || '').toLowerCase();
    for (const [key, emoji] of Object.entries(map)) {
      if (lower.includes(key)) return emoji;
    }
    return '📦';
  },

  _toast(msg, type = '') {
    const el = document.getElementById('toast');
    if (!el) return;
    el.textContent = msg;
    el.className = `toast show${type ? ' ' + type : ''}`;
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => {
      el.className = 'toast';
    }, 2800);
  },

  _bumpBadge() {
    const badge = document.getElementById('cartBadge');
    if (!badge) return;
    badge.classList.remove('bump');
    // Force reflow
    void badge.offsetWidth;
    badge.classList.add('bump');
    setTimeout(() => badge.classList.remove('bump'), 300);
  },
};

/* ═══════════════════════════════════════════════════════════════════════════
   BOOT
   ═══════════════════════════════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => Shop.init());
