import { prisma } from '@/lib/prisma';
import { ok, badRequest, notFound, serverError } from '@/lib/http';
import { requireAdminUser } from '@/lib/admin-guard';
import { z } from 'zod';

export const runtime = 'nodejs';

const bodySchema = z.object({
  name: z.string().min(1).max(50),
  values: z.array(z.string().min(1).max(50)).min(1),
  position: z.number().int().min(0).optional(),
});

export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const options = await prisma.productOption.findMany({
    where: { productId: id },
    orderBy: { position: 'asc' },
    include: { values: { orderBy: { position: 'asc' } } },
  });
  return ok(options);
}

export async function POST(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { user, error } = await requireAdminUser();
  if (error) return error;
  const { id } = await ctx.params;

  const product = await prisma.product.findUnique({ where: { id } });
  if (!product) return notFound('Product not found');

  const payload = await req.json().catch(() => null);
  const parsed = bodySchema.safeParse(payload);
  if (!parsed.success) return badRequest('Invalid payload', parsed.error.format());

  const { name, values, position } = parsed.data;

  try {
    const created = await prisma.productOption.create({
      data: {
        productId: id,
        name,
        position: position ?? 0,
        values: { create: values.map((v, i) => ({ value: v, position: i })) },
      },
      include: { values: true },
    });
    return ok(created, { status: 201 });
  } catch (e: any) {
    return serverError('Failed to create option', e);
  }
}
