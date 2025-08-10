import { prisma } from '@/lib/prisma';
import { ok, notFound } from '@/lib/http';

export const runtime = 'nodejs';

export async function GET(_req: Request, ctx: { params: Promise<{ slug: string }> }) {
  const { slug } = await ctx.params;

  const product = await prisma.product.findFirst({
    where: { slug, status: 'PUBLISHED' },
    include: {
      brand: true,
      categories: { include: { category: true } },
      images: { orderBy: { position: 'asc' } },
      options: { include: { values: { orderBy: { position: 'asc' } } }, orderBy: { position: 'asc' } },
      variants: {
        orderBy: { createdAt: 'asc' },
        include: {
          variantOptions: { include: { option: true, value: true } },
          stockLevels: true,
        },
      },
    },
  });

  if (!product) return notFound('Product not found');

  // Shape variants to include an option value map for easier client rendering
  const variants = product.variants.map(v => {
    const valueMap: Record<string, string> = {};
    for (const vo of v.variantOptions) {
      valueMap[vo.option.name] = vo.value.value;
    }
    return {
      id: v.id,
      sku: v.sku,
      title: v.title,
      priceCents: v.priceCents,
      currency: v.currency,
      compareAtCents: v.compareAtCents,
      isDefault: v.isDefault,
      values: valueMap,
      stock: v.stockLevels.reduce((sum, s) => sum + s.onHand - s.reserved, 0),
    };
  });

  const shaped = {
    id: product.id,
    title: product.title,
    slug: product.slug,
    description: product.description,
    brand: product.brand ? { id: product.brand.id, name: product.brand.name, slug: product.brand.slug } : null,
    images: product.images.map(i => ({ url: i.url, alt: i.alt })),
    categories: product.categories.map(pc => ({ id: pc.category.id, name: pc.category.name, slug: pc.category.slug })),
    options: product.options.map(o => ({ name: o.name, values: o.values.map(v => v.value) })),
    variants,
  };

  return ok(shaped, { headers: { 'Cache-Control': 'public, s-maxage=30' } });
}
