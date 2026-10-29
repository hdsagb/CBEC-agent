/**
 * 前端权限矩阵。
 *
 * 唯一依据是《部署验收测试计划》§6 权限矩阵，与后端 `require_role` 一一对应：
 * - 浏览类（要素/报价/报表/供应商/箱唛/Agent/工作台）：所有已登录用户
 * - 要素、供应商的新建/修改/复制/导入/模板下载：customs 及以上
 * - 删除要素/供应商、访问 /admin：仅 admin
 *
 * 报价、箱唛、Agent 按 §6 对全员开放，因此不做角色区分。
 */
export type Role = 'merchandiser' | 'customs' | 'admin'

export type Permission =
  | 'dashboard.view'
  | 'elements.read'
  | 'elements.write'
  | 'elements.delete'
  | 'quotes.use'
  | 'marks.use'
  | 'reports.read'
  | 'suppliers.read'
  | 'suppliers.write'
  | 'suppliers.delete'
  | 'agent.use'
  | 'admin.access'

export const ROLE_LABEL: Record<Role, string> = {
  merchandiser: '业务员',
  customs: '关务员',
  admin: '管理员',
}

const ALL_ROLES: readonly Role[] = ['merchandiser', 'customs', 'admin']
const CUSTOMS_AND_ABOVE: readonly Role[] = ['customs', 'admin']
const ADMIN_ONLY: readonly Role[] = ['admin']

export const PERMISSION_MATRIX: Record<Permission, readonly Role[]> = {
  'dashboard.view': ALL_ROLES,
  'elements.read': ALL_ROLES,
  'elements.write': CUSTOMS_AND_ABOVE,
  'elements.delete': ADMIN_ONLY,
  'quotes.use': ALL_ROLES,
  'marks.use': ALL_ROLES,
  'reports.read': ALL_ROLES,
  'suppliers.read': ALL_ROLES,
  'suppliers.write': CUSTOMS_AND_ABOVE,
  'suppliers.delete': ADMIN_ONLY,
  'agent.use': ALL_ROLES,
  'admin.access': ADMIN_ONLY,
}

/** 路由名 -> 权限；未列出的路由（登录、403）只校验登录态 */
export const ROUTE_PERMISSION: Record<string, Permission> = {
  agent: 'agent.use',
  dashboard: 'dashboard.view',
  elements: 'elements.read',
  quotes: 'quotes.use',
  marks: 'marks.use',
  reports: 'reports.read',
  suppliers: 'suppliers.read',
  admin: 'admin.access',
}

export function isRole(value: unknown): value is Role {
  return typeof value === 'string' && value in ROLE_LABEL
}

export function can(role: string | null | undefined, permission: Permission): boolean {
  return isRole(role) && PERMISSION_MATRIX[permission].includes(role)
}

export function roleLabel(role: string | null | undefined): string {
  return isRole(role) ? ROLE_LABEL[role] : (role ?? '')
}

/**
 * 从本地登录态读取角色，供路由守卫在 Pinia 初始化前同步判断。
 * 页面加载后 MainLayout 会调用 refreshMe 与后端对齐，避免角色被后台调整后仍沿用旧缓存。
 */
export function currentRole(): Role | null {
  try {
    const raw = localStorage.getItem('user')
    if (!raw) return null
    const role = (JSON.parse(raw) as { role?: unknown }).role
    return isRole(role) ? role : null
  } catch {
    return null
  }
}

export function permissionForRoute(name: unknown): Permission | null {
  return typeof name === 'string' && name in ROUTE_PERMISSION ? ROUTE_PERMISSION[name] : null
}
