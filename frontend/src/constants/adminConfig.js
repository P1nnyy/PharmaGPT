export const COMMON_UNITS = [
    'pieces',
    'ml',
    'L',
    'strip',
    'box',
    'tube',
    'vial',
    'ampoule',
    'g',
    'mg',
    'kg'
];

export const AVAILABLE_PERMISSIONS = [
    { id: 'all', label: 'Super Admin (All Access)', desc: 'Full system privileges' },
    { id: 'tab:scan', label: 'Scan Access', desc: 'Can upload and process invoices' },
    { id: 'tab:invoices', label: 'View Invoices', desc: 'Can see processed invoice list' },
    { id: 'tab:items', label: 'View Items', desc: 'Can browse product master' },
    { id: 'tab:inventory', label: 'View Inventory', desc: 'Can check stock levels' },
    { id: 'tab:history', label: 'View History', desc: 'Can see audit logs' },
    { id: 'tab:admin', label: 'System Admin', desc: 'Can manage settings and users' },
    { id: 'action:edit_items', label: 'Edit Items', desc: 'Can modify product details' },
    { id: 'action:edit_inventory', label: 'Edit Inventory', desc: 'Can perform stock updates' }
];

export const CATEGORY_TABS = [
    { id: 'categories', label: 'Item Categories', icon: 'Tags' },
    { id: 'roles', label: 'User Roles & Permissions', icon: 'Shield' }
];

export const DEFAULT_ROLE_PERMISSIONS = {
    'Admin': ['all'],
    'Manager': ['tab:scan', 'tab:invoices', 'tab:items', 'tab:inventory', 'tab:history', 'action:edit_items', 'action:edit_inventory'],
    'User': ['tab:scan', 'tab:invoices', 'tab:items', 'tab:history']
};
