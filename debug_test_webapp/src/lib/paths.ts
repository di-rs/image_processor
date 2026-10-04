// Deliberately reject escapes before URL parsing can normalize traversal away.
export function allowedMethods(path: string): string[] | null {
  if (/[\\%?#]/.test(path) || path.includes('..')) return null;
  if (['', 'health', 'debug/images', 'debug/summary'].includes(path)) return ['GET'];
  if (/^debug\/images\/[1-9]\d*$/.test(path)) return ['GET'];

  if (path === 'images/uploads') return ['POST'];
  if (/^images\/uploads\/[A-Za-z0-9_-]+$/.test(path)) return ['PUT'];
  if (/^images\/[1-9]\d*\/original$/.test(path)) return ['GET'];
  if (/^images\/[1-9]\d*$/.test(path)) return ['GET', 'PATCH', 'DELETE'];
  return null;
}
