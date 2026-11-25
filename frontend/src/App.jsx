import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  ShoppingBag,
  Package,
  Folder,
  CornerDownRight,
  Upload,
  Database,
  User,
  Trash2,
  Plus,
  Search,
  FileUp,
  Download,
  Image as ImageIcon,
  Edit3,
} from "lucide-react";
import { catalogApi } from "./services/api";
import ProductModal from "./components/ProductModal";
import "./App.css";

const FALLBACK_IMG =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(`
  <svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">
    <rect width="60" height="60" fill="#E2E8F0"/>
    <text x="50%" y="52%" dominant-baseline="middle" text-anchor="middle" fill="#475569" font-family="sans-serif" font-size="9" font-weight="bold">ITEM</text>
  </svg>
`);

const categoryHierarchyMap = {
  "Wireless Headphones": {
    path: "Electronics › Audio › Wireless Headphones",
    slug: "wireless-headphones",
    level: 2,
  },
  "Audio Speakers": {
    path: "Electronics › Audio › Audio Speakers",
    slug: "audio-speakers",
    level: 2,
  },
  Peripherals: {
    path: "Electronics › Computers › Peripherals",
    slug: "peripherals",
    level: 2,
  },
  Monitors: {
    path: "Electronics › Computers › Monitors",
    slug: "monitors",
    level: 2,
  },
  Smartwatches: {
    path: "Electronics › Wearables › Smartwatches",
    slug: "smartwatches",
    level: 2,
  },
  "Men's Footwear": {
    path: "Fashion › Footwear › Men's Footwear",
    slug: "mens-footwear",
    level: 2,
  },
  "Men's Apparel": {
    path: "Fashion › Clothing › Men's Apparel",
    slug: "mens-apparel",
    level: 2,
  },
};

export default function App() {
  const [activeView, setActiveView] = useState("products");
  const [apiConnected, setApiConnected] = useState(false);
  const [connectionMode, setConnectionMode] = useState("local");

  const [products, setProducts] = useState([]);
  const [dbCategories, setDbCategories] = useState([]);
  const [importJobs, setImportJobs] = useState([]);
  const [importErrors, setImportErrors] = useState([]);
  const [lastMapping, setLastMapping] = useState(null);

  // Unified Loading States
  const [initialLoading, setInitialLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [savingCategory, setSavingCategory] = useState(false);
  const [busyRowId, setBusyRowId] = useState(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("ALL");
  const [stockFilter, setStockFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState("ALL");

  // Modal
  const [modalOpen, setModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);

  // Category Form
  const [catName, setCatName] = useState("");
  const [catParent, setCatParent] = useState("");
  const [catSlug, setCatSlug] = useState("");

  // ER Diagram State
  const [erdSrc, setErdSrc] = useState("/er_diagram.png");
  const [erdLoaded, setErdLoaded] = useState(false);

  const csvInputRef = useRef(null);
  const erdInputRef = useRef(null);

  const syncFromBackend = useCallback(async () => {
    setSyncing(true);
    try {
      const conn = await catalogApi.health();
      setConnectionMode(conn.mode);
      setApiConnected(true);

      const [prodRes, catRes, jobsRes] = await Promise.all([
        catalogApi.listProducts({ limit: 500 }),
        catalogApi.listCategories(),
        catalogApi.listImportJobs(),
      ]);

      setProducts(prodRes.data.items || []);
      setDbCategories(catRes.data.categories || []);

      const jobs = jobsRes.data.jobs || [];
      setImportJobs(jobs);
      const allErrs = [];
      jobs.forEach((j) => {
        (j.errors || []).forEach((err) => allErrs.push(err));
      });
      setImportErrors(allErrs);
    } catch {
      setApiConnected(false);
    } finally {
      setSyncing(false);
      setInitialLoading(false);
    }
  }, []);

  useEffect(() => {
    syncFromBackend();
  }, [syncFromBackend]);

  const buildHierarchyNodes = () => {
    const nodes = [];
    const seen = new Set();

    const addNode = (path, slug, level, count = 0) => {
      if (seen.has(slug)) return;
      seen.add(slug);
      nodes.push({ path, slug, level, count });
    };

    dbCategories.forEach((c) => {
      const mapped = categoryHierarchyMap[c.name];
      if (mapped) {
        const parts = mapped.path.split(" › ");
        if (parts.length === 3) {
          addNode(
            parts[0],
            parts[0].toLowerCase().replace(/[^a-z0-9]+/g, "-"),
            0,
          );
          addNode(
            `${parts[0]} › ${parts[1]}`,
            parts[1].toLowerCase().replace(/[^a-z0-9]+/g, "-"),
            1,
          );
        }
        addNode(mapped.path, c.slug, mapped.level, c.product_count);
      } else {
        const parent = dbCategories.find((x) => x.id === c.parent_id);
        addNode(
          parent ? `${parent.name} › ${c.name}` : c.name,
          c.slug,
          parent ? 1 : 0,
          c.product_count,
        );
      }
    });

    return nodes;
  };

  const hierarchyNodes = buildHierarchyNodes();

  const filteredProducts = products.filter((p) => {
    const q = searchQuery.toLowerCase();
    const matchText =
      p.title.toLowerCase().includes(q) ||
      p.external_id.toLowerCase().includes(q) ||
      p.brand.toLowerCase().includes(q);
    const catName = p.category?.name || "General";
    const matchCat = categoryFilter === "ALL" || catName === categoryFilter;
    const matchStk = stockFilter === "ALL" || p.stock_status === stockFilter;
    const matchSts = statusFilter === "ALL" || p.status === statusFilter;
    return matchText && matchCat && matchStk && matchSts;
  });

  const totalCount = products.length;
  const availableCount = products.filter(
    (p) => p.status === "ACTIVE" && p.stock_status !== "OUT_OF_STOCK",
  ).length;
  const lowStockCount = products.filter(
    (p) => p.stock_status !== "IN_STOCK",
  ).length;
  const inactiveCount = products.filter((p) => p.status !== "ACTIVE").length;

  const handleResetAll = async () => {
    if (!window.confirm("Clear all products, categories, and import logs?"))
      return;
    setResetting(true);
    try {
      await catalogApi.resetAll();
      setLastMapping(null);
      await syncFromBackend();
    } finally {
      setResetting(false);
    }
  };

  const handleSaveProduct = async (payload, productId) => {
    setSyncing(true);
    try {
      if (productId) {
        await catalogApi.updateProduct(productId, payload);
      } else {
        await catalogApi.createProduct(payload);
      }
      await syncFromBackend();
    } finally {
      setSyncing(false);
    }
  };

  const handleDeleteProduct = async (p) => {
    if (!window.confirm(`Delete "${p.title}" (${p.external_id})?`)) return;
    setBusyRowId(p.id);
    try {
      await catalogApi.deleteProduct(p.id);
      await syncFromBackend();
    } finally {
      setBusyRowId(null);
    }
  };

  const cycleStock = async (p) => {
    const order = ["IN_STOCK", "LOW_STOCK", "OUT_OF_STOCK"];
    const nextStock = order[(order.indexOf(p.stock_status) + 1) % order.length];
    setBusyRowId(p.id);
    try {
      await catalogApi.updateProduct(p.id, { stock_status: nextStock });
      await syncFromBackend();
    } finally {
      setBusyRowId(null);
    }
  };

  const toggleActive = async (p) => {
    const nextStatus = p.status === "ACTIVE" ? "INACTIVE" : "ACTIVE";
    setBusyRowId(p.id);
    try {
      await catalogApi.updateProduct(p.id, { status: nextStatus });
      await syncFromBackend();
    } finally {
      setBusyRowId(null);
    }
  };

  const handleAddCategory = async (e) => {
    e.preventDefault();
    const slug = catSlug.trim().toLowerCase().replace(/\s+/g, "-");
    setSavingCategory(true);
    try {
      await catalogApi.createCategory({
        name: catName.trim(),
        slug,
        parent_id: catParent || null,
      });
      setCatName("");
      setCatParent("");
      setCatSlug("");
      await syncFromBackend();
    } finally {
      setSavingCategory(false);
    }
  };

  const downloadSampleCsv = () => {
    const csv = [
      "external_id,title,category,brand,price,stock_status",
      "SKU-1001,Sony WH-1000XM5 Wireless Headphones,Wireless Headphones,Sony,299.00,IN_STOCK",
      "SKU-1002,Apple AirPods Pro 2nd Gen,Wireless Headphones,Apple,249.00,IN_STOCK",
      "SKU-1003,Logitech MX Master 3S Wireless Mouse,Peripherals,Logitech,99.00,IN_STOCK",
      "SKU-1004,Dell UltraSharp 27-Inch 4K Monitor,Monitors,Dell,449.00,IN_STOCK",
      "SKU-1005,Nike Air Zoom Pegasus 40 Running Shoes,Men's Footwear,Nike,130.00,IN_STOCK",
    ].join("\n");

    const blob = new Blob([csv], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "store_catalog_template.csv";
    a.click();
  };

  const handleCsvUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    try {
      const res = await catalogApi.importCsv(file, 1000);
      const report = res.data;

      // 1. Update UI immediately from the POST response
      setLastMapping(report.detected_mapping || null);
      setImportJobs((prev) => [
        {
          job_id: report.job_id,
          filename: report.filename,
          status: report.status,
          total_rows: report.total_rows,
          valid_rows: report.valid_rows,
          error_rows: report.error_rows,
          errors: report.errors || [],
          created_at: new Date().toISOString(),
        },
        ...prev,
      ]);
      if (report.errors?.length) {
        setImportErrors((prev) => [...report.errors, ...prev]);
      }

      // 2. Refresh full products, categories, and audit logs from PostgreSQL
      await syncFromBackend();
    } catch (err) {
      alert(err.response?.data?.detail || "CSV upload failed");
    } finally {
      setImporting(false);
      e.target.value = "";
    }
  };

  const handleErdImagePick = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setErdSrc(URL.createObjectURL(file));
    setErdLoaded(true);
  };

  const pageTitles = {
    products: "Products",
    categories: "Categories",
    import: "Bulk Import",
    erd: "ER Diagram",
  };

  const uniqueCategoryNames = [
    ...new Set(products.map((p) => p.category?.name || "General")),
  ];

  const isAnyBusy =
    syncing || importing || resetting || savingCategory || Boolean(busyRowId);

  return (
    <div className="app-layout">
      {isAnyBusy && <div className="top-loader-bar" />}

      {initialLoading && (
        <div className="page-loader-overlay">
          <div className="loader-spinner-ring" />
          <div className="page-loader-text">Loading Catalog Admin...</div>
          <div className="page-loader-sub">
            Connecting to FastAPI &amp; PostgreSQL
          </div>
        </div>
      )}

      {/* LEFT SIDEBAR */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo">
            <ShoppingBag size={20} strokeWidth={2.2} />
          </div>
          <div>
            <h2>Online Shopping</h2>
            <span>Catalog Admin</span>
          </div>
        </div>

        <nav className="side-nav">
          <button
            className={`nav-item ${activeView === "products" ? "active" : ""}`}
            onClick={() => setActiveView("products")}
          >
            <Package size={17} />
            Products
          </button>
          <button
            className={`nav-item ${activeView === "categories" ? "active" : ""}`}
            onClick={() => setActiveView("categories")}
          >
            <Folder size={17} />
            Categories
          </button>
          <button
            className={`nav-item ${activeView === "import" ? "active" : ""}`}
            onClick={() => setActiveView("import")}
          >
            <Upload size={17} />
            Bulk Import
          </button>
          <button
            className={`nav-item ${activeView === "erd" ? "active" : ""}`}
            onClick={() => setActiveView("erd")}
          >
            <Database size={17} />
            ER Diagram
          </button>
        </nav>

        <div className="sidebar-footer">
          <div className={`api-status ${apiConnected ? "" : "offline"}`}>
            <span className="dot" />
            {!apiConnected
              ? "Standalone Mode"
              : connectionMode === "cloud"
                ? "Cloud API + Supabase"
                : "FastAPI Connected"}
          </div>
          <div className="user-chip">
            <div className="avatar">
              <User size={16} />
            </div>
            <div>
              <strong>Catalog Manager</strong>
              <small>admin@onlineshopping.com</small>
            </div>
          </div>
        </div>
      </aside>

      {/* MAIN CONTENT */}
      <div className="main-area">
        <header className="topbar">
          <h1>{pageTitles[activeView]}</h1>
          {activeView === "products" && (
            <div className="topbar-actions">
              <button
                className="btn-outline"
                onClick={handleResetAll}
                disabled={resetting}
              >
                {resetting ? (
                  <span className="btn-spinner" />
                ) : (
                  <Trash2 size={15} />
                )}
                {resetting ? "Resetting..." : "Reset Data"}
              </button>
              <button
                className="btn-primary"
                onClick={() => {
                  setEditingProduct(null);
                  setModalOpen(true);
                }}
              >
                <Plus size={15} strokeWidth={2.2} />
                Add Product
              </button>
            </div>
          )}
        </header>

        {/* =====================================
           PAGE 1: PRODUCTS
           ===================================== */}
        {activeView === "products" && (
          <section>
            <div className="stats-grid">
              <div className="stat-card">
                <span className="stat-label">Total Products</span>
                <strong className="stat-num">{totalCount}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">
                  AI Recommendable (Active &amp; In-Stock)
                </span>
                <strong className="stat-num text-green">
                  {availableCount}
                </strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Low / Out of Stock</span>
                <strong className="stat-num text-amber">{lowStockCount}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Inactive / Excluded</span>
                <strong className="stat-num text-muted">{inactiveCount}</strong>
              </div>
            </div>

            <div className="card">
              <div className="filter-bar">
                <div className="search-input-wrap">
                  <Search size={15} />
                  <input
                    type="text"
                    placeholder="Search by product name, SKU, or brand..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
                <select
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                >
                  <option value="ALL">All Categories</option>
                  {uniqueCategoryNames.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
                <select
                  value={stockFilter}
                  onChange={(e) => setStockFilter(e.target.value)}
                >
                  <option value="ALL">All Stock Status</option>
                  <option value="IN_STOCK">In Stock</option>
                  <option value="LOW_STOCK">Low Stock</option>
                  <option value="OUT_OF_STOCK">Out of Stock</option>
                </select>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                >
                  <option value="ALL">All Visibility</option>
                  <option value="ACTIVE">Active</option>
                  <option value="INACTIVE">Inactive</option>
                </select>
              </div>

              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Product</th>
                      <th>SKU</th>
                      <th>Category</th>
                      <th>Brand</th>
                      <th>Price</th>
                      <th>Stock</th>
                      <th>AI Eligibility</th>
                      <th>Store Visibility</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {syncing && products.length === 0 ? (
                      Array.from({ length: 5 }).map((_, idx) => (
                        <tr key={`skel-${idx}`}>
                          <td>
                            <div className="prod-cell">
                              <div className="skeleton-thumb" />
                              <div style={{ flex: 1 }}>
                                <div
                                  className="skeleton-bar"
                                  style={{ width: "65%", marginBottom: 6 }}
                                />
                                <div
                                  className="skeleton-bar"
                                  style={{ width: "40%", height: 10 }}
                                />
                              </div>
                            </div>
                          </td>
                          <td>
                            <div
                              className="skeleton-bar"
                              style={{ width: 70 }}
                            />
                          </td>
                          <td>
                            <div
                              className="skeleton-bar"
                              style={{ width: 90 }}
                            />
                          </td>
                          <td>
                            <div
                              className="skeleton-bar"
                              style={{ width: 65 }}
                            />
                          </td>
                          <td>
                            <div
                              className="skeleton-bar"
                              style={{ width: 55 }}
                            />
                          </td>
                          <td>
                            <div
                              className="skeleton-bar"
                              style={{ width: 70 }}
                            />
                          </td>
                          <td>
                            <div
                              className="skeleton-bar"
                              style={{ width: 65 }}
                            />
                          </td>
                          <td>
                            <div
                              className="skeleton-bar"
                              style={{ width: 75 }}
                            />
                          </td>
                          <td>
                            <div
                              className="skeleton-bar"
                              style={{ width: 45 }}
                            />
                          </td>
                        </tr>
                      ))
                    ) : filteredProducts.length === 0 ? (
                      <tr>
                        <td colSpan="9" className="empty-cell">
                          No products in catalog yet. Click{" "}
                          <strong>Add Product</strong> or upload your CSV file
                          in <strong>Bulk Import</strong>.
                        </td>
                      </tr>
                    ) : (
                      filteredProducts.map((p) => {
                        const isActive = p.status === "ACTIVE";
                        const eligible =
                          isActive && p.stock_status !== "OUT_OF_STOCK";
                        const attrsString =
                          Object.entries(p.attributes || {})
                            .map(([k, v]) => `${k}: ${v}`)
                            .join(" • ") || "Catalog Item";

                        return (
                          <tr
                            key={p.id}
                            className={busyRowId === p.id ? "row-updating" : ""}
                          >
                            <td>
                              <div className="prod-cell">
                                <img
                                  src={p.image_url || FALLBACK_IMG}
                                  alt=""
                                  className="prod-thumb"
                                  onError={(e) => {
                                    e.currentTarget.src = FALLBACK_IMG;
                                  }}
                                />
                                <div>
                                  <strong>{p.title}</strong>
                                  <div className="prod-sub">{attrsString}</div>
                                </div>
                              </div>
                            </td>
                            <td>
                              <strong>{p.external_id}</strong>
                            </td>
                            <td>{p.category?.name || "General"}</td>
                            <td>{p.brand}</td>
                            <td>
                              <strong>${p.price.toFixed(2)}</strong>
                            </td>
                            <td>
                              {p.stock_status === "IN_STOCK" ? (
                                <span
                                  className="badge badge-green"
                                  onClick={() => cycleStock(p)}
                                  title="Click to change stock"
                                >
                                  In Stock
                                </span>
                              ) : p.stock_status === "LOW_STOCK" ? (
                                <span
                                  className="badge badge-amber"
                                  onClick={() => cycleStock(p)}
                                  title="Click to change stock"
                                >
                                  Low Stock
                                </span>
                              ) : (
                                <span
                                  className="badge badge-red"
                                  onClick={() => cycleStock(p)}
                                  title="Click to change stock"
                                >
                                  Out of Stock
                                </span>
                              )}
                            </td>
                            <td>
                              {eligible ? (
                                <span className="badge badge-green">
                                  Eligible
                                </span>
                              ) : (
                                <span className="badge badge-red">
                                  Excluded
                                </span>
                              )}
                            </td>
                            <td>
                              <div
                                className="switch-wrap"
                                onClick={() => toggleActive(p)}
                              >
                                <div
                                  className={`switch ${isActive ? "on" : ""}`}
                                />
                                <span>{isActive ? "Active" : "Inactive"}</span>
                              </div>
                            </td>
                            <td>
                              <div className="action-btns">
                                <button
                                  className="icon-btn"
                                  title="Edit Product"
                                  onClick={() => {
                                    setEditingProduct(p);
                                    setModalOpen(true);
                                  }}
                                >
                                  <Edit3 size={15} />
                                </button>
                                <button
                                  className="icon-btn danger"
                                  title="Delete Product"
                                  onClick={() => handleDeleteProduct(p)}
                                >
                                  <Trash2 size={15} />
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        )}

        {/* =====================================
           PAGE 2: CATEGORIES
           ===================================== */}
        {activeView === "categories" && (
          <section>
            <div className="two-col">
              <div className="card">
                <div className="card-head">
                  <h3>Category Hierarchy</h3>
                  <span className="pill-count">
                    {hierarchyNodes.length} Categories
                  </span>
                </div>
                <div className="tree-box">
                  {hierarchyNodes.length === 0 ? (
                    <div className="empty-cell">
                      No categories created yet. Upload a CSV or use the form on
                      the right to build your category tree.
                    </div>
                  ) : (
                    hierarchyNodes.map((c) => (
                      <div
                        key={c.slug}
                        className="tree-row"
                        style={{ paddingLeft: `${12 + c.level * 18}px` }}
                      >
                        <span className="tree-label">
                          {c.level > 0 ? (
                            <CornerDownRight size={14} color="#64748B" />
                          ) : (
                            <Folder size={15} color="#167D8D" />
                          )}
                          <strong>{c.path}</strong>
                        </span>
                        <span className="slug-tag">{c.slug}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="card">
                <div className="card-head">
                  <h3>Create Category</h3>
                </div>
                <form onSubmit={handleAddCategory} className="clean-form">
                  <div className="field">
                    <label>Category Name *</label>
                    <input
                      type="text"
                      placeholder="e.g., Electronics"
                      value={catName}
                      onChange={(e) => setCatName(e.target.value)}
                      required
                    />
                  </div>
                  <div className="field">
                    <label>Parent Category</label>
                    <select
                      value={catParent}
                      onChange={(e) => setCatParent(e.target.value)}
                    >
                      <option value="">None (Top-Level Department)</option>
                      {dbCategories.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label>URL Slug *</label>
                    <input
                      type="text"
                      placeholder="e.g., electronics"
                      value={catSlug}
                      onChange={(e) => setCatSlug(e.target.value)}
                      required
                    />
                  </div>
                  <button
                    type="submit"
                    className="btn-primary full"
                    disabled={savingCategory}
                  >
                    {savingCategory && <span className="btn-spinner" />}
                    {savingCategory ? "Saving Category..." : "Save Category"}
                  </button>
                </form>
              </div>
            </div>
          </section>
        )}

        {/* =====================================
           PAGE 3: BULK IMPORT
           ===================================== */}
        {activeView === "import" && (
          <section>
            <div className="card upload-card">
              <div
                className="upload-zone"
                style={{
                  opacity: importing ? 0.7 : 1,
                  pointerEvents: importing ? "none" : "auto",
                }}
                onClick={() => csvInputRef.current?.click()}
              >
                <div className="upload-icon-circle">
                  {importing ? (
                    <span className="btn-spinner" />
                  ) : (
                    <FileUp size={24} />
                  )}
                </div>
                <h3>
                  {importing
                    ? "Importing & Normalizing CSV..."
                    : "Upload Product Catalog CSV (or Any Kaggle Dataset)"}
                </h3>
                <p>
                  {importing
                    ? "Please wait while rows are validated and batch-inserted into PostgreSQL."
                    : "Click here to select your .csv file — supports both our standard template and raw Kaggle e-commerce CSVs (auto-maps headers & currencies)"}
                </p>
                <input
                  type="file"
                  ref={csvInputRef}
                  accept=".csv"
                  hidden
                  onChange={handleCsvUpload}
                />
              </div>
              <div className="upload-actions">
                <div className="mapping-strip">
                  {lastMapping && (
                    <>
                      <strong>Last Auto-Mapping:</strong>
                      {Object.entries(lastMapping).map(([target, src]) => (
                        <span key={target} className="slug-tag">
                          {target} ← {src || "auto"}
                        </span>
                      ))}
                    </>
                  )}
                </div>
                <button className="btn-outline" onClick={downloadSampleCsv}>
                  <Download size={15} />
                  Download Sample CSV Template
                </button>
              </div>
            </div>

            <div className="two-col" style={{ marginTop: "20px" }}>
              <div className="card">
                <div className="card-head">
                  <h3>Import Job History</h3>
                </div>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>File Name</th>
                      <th>Status</th>
                      <th>Total</th>
                      <th>Imported</th>
                      <th>Failed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {importJobs.length === 0 ? (
                      <tr>
                        <td colSpan="5" className="empty-cell">
                          No CSV files uploaded yet.
                        </td>
                      </tr>
                    ) : (
                      importJobs.map((j) => (
                        <tr key={j.job_id}>
                          <td>
                            <strong>{j.filename}</strong>
                          </td>
                          <td>
                            <span
                              className={`badge ${
                                j.error_rows > 0 ? "badge-amber" : "badge-green"
                              }`}
                            >
                              {j.error_rows > 0
                                ? "Completed with Errors"
                                : "Completed"}
                            </span>
                          </td>
                          <td>{j.total_rows}</td>
                          <td className="text-green">
                            <strong>{j.valid_rows}</strong>
                          </td>
                          <td className="text-red">
                            <strong>{j.error_rows}</strong>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              <div className="card">
                <div className="card-head">
                  <h3>Row Validation Errors</h3>
                  <span className="badge badge-red">
                    {importErrors.length} Errors
                  </span>
                </div>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Row</th>
                      <th>SKU</th>
                      <th>Validation Issue</th>
                    </tr>
                  </thead>
                  <tbody>
                    {importErrors.length === 0 ? (
                      <tr>
                        <td colSpan="3" className="empty-cell">
                          No validation errors recorded.
                        </td>
                      </tr>
                    ) : (
                      importErrors.map((err, i) => (
                        <tr key={i}>
                          <td>
                            <strong>#{err.row}</strong>
                          </td>
                          <td>
                            <code>{err.external_id}</code>
                          </td>
                          <td>{err.issue}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        )}

        {/* =====================================
           PAGE 4: ER DIAGRAM (IMAGE VIEWER)
           ===================================== */}
        {activeView === "erd" && (
          <section>
            <div className="card">
              <div className="card-head">
                <div>
                  <h3>
                    Database Entity-Relationship Diagram (PostgreSQL Schema)
                  </h3>
                  <p className="muted-intro">
                    5-table normalized schema: <code>products</code>,{" "}
                    <code>categories</code>, <code>product_categories</code>,{" "}
                    <code>product_attributes</code>, and{" "}
                    <code>catalog_import_jobs</code>.
                  </p>
                </div>
                <div>
                  <input
                    type="file"
                    ref={erdInputRef}
                    accept="image/*"
                    hidden
                    onChange={handleErdImagePick}
                  />
                  <button
                    className="btn-outline"
                    onClick={() => erdInputRef.current?.click()}
                  >
                    <ImageIcon size={15} />
                    Load ER Diagram Image
                  </button>
                </div>
              </div>

              <div className="erd-image-frame">
                <img
                  src={erdSrc}
                  alt="Entity-Relationship Diagram"
                  style={{ display: erdLoaded ? "block" : "none" }}
                  onLoad={() => setErdLoaded(true)}
                  onError={() => setErdLoaded(false)}
                />
                {!erdLoaded && (
                  <div className="erd-placeholder">
                    <Database size={36} color="#167D8D" strokeWidth={1.8} />
                    <h4>
                      Place <code>er_diagram.png</code> in{" "}
                      <code>frontend/public/</code>
                    </h4>
                    <p>
                      Or click <strong>Load ER Diagram Image</strong> in the top
                      right to select your downloaded ER diagram image directly.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </section>
        )}
      </div>

      <ProductModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onSave={handleSaveProduct}
        initialProduct={editingProduct}
      />
    </div>
  );
}
