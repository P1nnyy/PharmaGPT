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
    'view_invoices',
    'edit_invoices',
    'delete_invoices',
    'manage_users',
    'manage_roles',
    'manage_categories'
];

export const CATEGORY_TABS = [
    { id: 'overview', label: 'Overview' },
    { id: 'units', label: 'Units' },
    { id: 'permissions', label: 'Permissions' }
];

export const DEFAULT_ROLE_PERMISSIONS = {
    'Admin': ['view_invoices', 'edit_invoices', 'delete_invoices', 'manage_users', 'manage_roles', 'manage_categories'],
    'Manager': ['view_invoices', 'edit_invoices'],
    'User': ['view_invoices']
};
