
export const getImageUrl = (path) => {
    const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

    if (!path) return null;
    if (path.startsWith('http')) return path; // R2/S3 Direct Link

    // If we are on the tunnel (pharmagpt.co) or production, use relative path 
    // to leverage the Vite/Nginx Proxy which handles HTTPS correctly.
    if (API_BASE_URL === '' || window.location.hostname.includes('pharmagpt') || window.location.hostname.includes('cloudflare')) {
        // Relative path, but ensure it starts with / if path doesn't
        return path.startsWith('/') ? path : `/${path}`;
    }

    // Fallback for local dev without proxy (rare, but safe)
    return `${API_BASE_URL}${path.startsWith('/') ? '' : '/'}${path}`;
};
