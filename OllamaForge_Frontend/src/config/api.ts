/**
 * API Configuration
 * Change API_BASE to point to your backend server.
 */
export const API_BASE = "http://127.0.0.1:5000";

export const API_ENDPOINTS = {
  HEALTH: `${API_BASE}/health`,
  INIT_SESSION: `${API_BASE}/api/init_session`,
  SET_SOURCE: `${API_BASE}/api/set_source`,
  SET_MODEL: `${API_BASE}/api/set_model`,
  CHAT: `${API_BASE}/api/chat`,
  UPLOAD_PDF: `${API_BASE}/api/upload_pdf`,
  UPLOAD_DOCX: `${API_BASE}/api/upload_docx`,
  UPLOAD_WEBSITE: `${API_BASE}/api/upload_website`,
  INIT_DATABASE: `${API_BASE}/api/init_database`,
} as const;
