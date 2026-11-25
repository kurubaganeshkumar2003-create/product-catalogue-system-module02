import axios from "axios";

const CLOUD_API_URL = import.meta.env.VITE_API_BASE_URL || "";
const LOCAL_API_URL = "http://127.0.0.1:8000/api/v1";
const ADMIN_TOKEN =
  import.meta.env.VITE_ADMIN_TOKEN || "dev-catalog-admin-token";

let activeBaseUrl = CLOUD_API_URL || LOCAL_API_URL;
let activeMode = CLOUD_API_URL ? "cloud" : "local";

const api = axios.create({
  baseURL: activeBaseUrl,
  timeout: 15000,
  headers: {
    "X-Admin-Token": ADMIN_TOKEN,
  },
});

export function getActiveConnectionInfo() {
  return { baseUrl: activeBaseUrl, mode: activeMode };
}

export async function resolveBestBackend() {
  if (CLOUD_API_URL) {
    try {
      await axios.get(`${CLOUD_API_URL}/health`, {
        params: { _t: Date.now() },
        timeout: 4000,
      });
      activeBaseUrl = CLOUD_API_URL;
      activeMode = "cloud";
      api.defaults.baseURL = activeBaseUrl;
      return getActiveConnectionInfo();
    } catch {
      // Cloud unreachable or sleeping -> automatically fall back to localhost
    }
  }

  await axios.get(`${LOCAL_API_URL}/health`, {
    params: { _t: Date.now() },
    timeout: 2500,
  });
  activeBaseUrl = LOCAL_API_URL;
  activeMode = "local";
  api.defaults.baseURL = activeBaseUrl;
  return getActiveConnectionInfo();
}

export const catalogApi = {
  health: () => resolveBestBackend(),
  listProducts: (params = {}) =>
    api.get("/products", { params: { ...params, _t: Date.now() } }),
  getProduct: (id) =>
    api.get(`/products/${id}`, { params: { _t: Date.now() } }),
  createProduct: (payload) => api.post("/admin/products", payload),
  updateProduct: (id, payload) => api.patch(`/admin/products/${id}`, payload),
  deleteProduct: (id) => api.delete(`/admin/products/${id}`),
  importCsv: (file, maxRows = 1000) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.post(`/admin/catalog/import?max_rows=${maxRows}`, formData);
  },
  listImportJobs: () =>
    api.get("/admin/catalog/import-jobs", { params: { _t: Date.now() } }),
  listCategories: () => api.get("/categories", { params: { _t: Date.now() } }),
  createCategory: (payload) => api.post("/categories", payload),
  resetAll: () => api.delete("/admin/reset"),
};

export default api;
