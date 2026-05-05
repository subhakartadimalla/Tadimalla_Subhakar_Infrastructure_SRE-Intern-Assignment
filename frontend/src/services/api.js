import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function normalizeDetail(detail) {
  if (detail == null) return "Request failed";
  if (typeof detail === "string") return detail;
  try {
    return JSON.stringify(detail);
  } catch {
    return String(detail);
  }
}

export const api = axios.create({
  baseURL,
  timeout: 15_000,
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Normalize Axios error into a predictable shape for the UI.
    const status = error?.response?.status;
    const detail = normalizeDetail(error?.response?.data?.detail ?? error?.message);

    // Keep logs lightweight but useful in production debugging.
    // eslint-disable-next-line no-console
    console.error("API error", { status, detail, url: error?.config?.url, method: error?.config?.method });

    return Promise.reject({
      status,
      detail,
      raw: error,
    });
  },
);

