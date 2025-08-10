import { prisma } from '@/lib/prisma';

export async function getDefaultWarehouseId(): Promise<string> {
  const wh = await prisma.warehouse.findFirst({ where: { isDefault: true } });
  if (!wh) throw new Error('No default warehouse found. Create one first.');
  return wh.id;
}
