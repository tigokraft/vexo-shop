import { prisma } from '@/lib/prisma';

export async function getProductOptionsWithValues(productId: string) {
  return prisma.productOption.findMany({
    where: { productId },
    orderBy: { position: 'asc' },
    include: { values: { orderBy: { position: 'asc' } } },
  });
}

export function variantTitleFromMap(productTitle: string, valuesByName: Record<string, string>) {
  const parts = Object.entries(valuesByName).map(([k, v]) => `${v}`);
  return `${productTitle} - ${parts.join(' / ')}`.trim();
}
