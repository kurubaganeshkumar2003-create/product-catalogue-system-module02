import React, { useState, useEffect } from "react";
import { X } from "lucide-react";

export default function ProductModal({
  isOpen,
  onClose,
  onSave,
  initialProduct,
}) {
  const isEdit = Boolean(initialProduct);

  const [title, setTitle] = useState("");
  const [sku, setSku] = useState("");
  const [category, setCategory] = useState("");
  const [brand, setBrand] = useState("");
  const [price, setPrice] = useState("");
  const [stock, setStock] = useState("IN_STOCK");
  const [imageUrl, setImageUrl] = useState("");
  const [attrsText, setAttrsText] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (initialProduct) {
      setTitle(initialProduct.title || "");
      setSku(initialProduct.external_id || "");
      setCategory(initialProduct.category?.name || "");
      setBrand(initialProduct.brand || "");
      setPrice(initialProduct.price ?? "");
      setStock(initialProduct.stock_status || "IN_STOCK");
      setImageUrl(initialProduct.image_url || "");
      const formatted = Object.entries(initialProduct.attributes || {})
        .map(([k, v]) => `${k}: ${v}`)
        .join(", ");
      setAttrsText(formatted);
    } else {
      setTitle("");
      setSku("");
      setCategory("");
      setBrand("");
      setPrice("");
      setStock("IN_STOCK");
      setImageUrl("");
      setAttrsText("");
    }
    setError("");
  }, [initialProduct, isOpen]);

  if (!isOpen) return null;

  const parseAttributes = (raw) => {
    const out = {};
    if (!raw.trim()) return out;
    raw.split(",").forEach((pair) => {
      const idx = pair.indexOf(":");
      if (idx > -1) {
        const k = pair.slice(0, idx).trim();
        const v = pair.slice(idx + 1).trim();
        if (k && v) out[k] = v;
      } else if (pair.trim()) {
        out["specs"] = pair.trim();
      }
    });
    return out;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    const numPrice = parseFloat(price);
    if (isNaN(numPrice) || numPrice <= 0) {
      setError("Price must be greater than $0.00.");
      return;
    }

    setSaving(true);
    try {
      const payload = {
        external_id: sku.trim(),
        title: title.trim(),
        category: category.trim(),
        brand: brand.trim(),
        price: numPrice,
        stock_status: stock,
        image_url: imageUrl.trim() || null,
        attributes: parseAttributes(attrsText),
      };
      await onSave(payload, isEdit ? initialProduct.id : null);
      onClose();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Failed to save product");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-box">
        <div className="modal-head">
          <h3>
            {isEdit
              ? `Edit Product (${initialProduct.external_id})`
              : "Add New Product"}
          </h3>
          <button
            type="button"
            className="icon-btn"
            onClick={onClose}
            disabled={saving}
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="clean-form">
          <div className="row-2">
            <div className="field">
              <label>Product Title *</label>
              <input
                type="text"
                placeholder="e.g., Sony WH-1000XM5 Headphones"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                disabled={saving}
                required
              />
            </div>
            <div className="field">
              <label>SKU Code *</label>
              <input
                type="text"
                placeholder="e.g., SKU-1001"
                value={sku}
                disabled={isEdit || saving}
                onChange={(e) => setSku(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="row-2">
            <div className="field">
              <label>Category *</label>
              <input
                type="text"
                placeholder="e.g., Wireless Headphones"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                disabled={saving}
                required
              />
            </div>
            <div className="field">
              <label>Brand *</label>
              <input
                type="text"
                placeholder="e.g., Sony"
                value={brand}
                onChange={(e) => setBrand(e.target.value)}
                disabled={saving}
                required
              />
            </div>
          </div>

          <div className="row-2">
            <div className="field">
              <label>Price ($) *</label>
              <input
                type="number"
                step="0.01"
                placeholder="e.g., 299.00"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                disabled={saving}
                required
              />
            </div>
            <div className="field">
              <label>Stock Status *</label>
              <select
                value={stock}
                onChange={(e) => setStock(e.target.value)}
                disabled={saving}
              >
                <option value="IN_STOCK">In Stock</option>
                <option value="LOW_STOCK">Low Stock</option>
                <option value="OUT_OF_STOCK">Out of Stock</option>
              </select>
            </div>
          </div>

          <div className="field">
            <label>Image URL (Optional — falls back safely if broken)</label>
            <input
              type="text"
              placeholder="https://example.com/product.jpg"
              value={imageUrl}
              onChange={(e) => setImageUrl(e.target.value)}
              disabled={saving}
            />
          </div>

          <div className="field">
            <label>
              Key Attributes (Optional, e.g., Color: Black, Battery: 30h)
            </label>
            <input
              type="text"
              placeholder="Color: Black, Battery: 30h"
              value={attrsText}
              onChange={(e) => setAttrsText(e.target.value)}
              disabled={saving}
            />
          </div>

          {error && <div className="alert-error">{error}</div>}

          <div className="modal-foot">
            <button
              type="button"
              className="btn-outline"
              onClick={onClose}
              disabled={saving}
            >
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={saving}>
              {saving && <span className="btn-spinner" />}
              {saving ? "Saving..." : isEdit ? "Save Changes" : "Save Product"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
