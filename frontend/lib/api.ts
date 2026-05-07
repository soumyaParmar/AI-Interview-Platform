const DEFAULT_API_BASE_URL = 'http://localhost:8000/api/v2';
const DEFAULT_SOCKET_URL = 'http://localhost:8000';

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_BASE_URL;

export const SOCKET_URL =
  process.env.NEXT_PUBLIC_SOCKET_URL || DEFAULT_SOCKET_URL;

export const apiUrl = (path: string) => {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
};
