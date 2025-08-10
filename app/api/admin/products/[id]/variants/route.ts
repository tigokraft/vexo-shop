import { prisma } from '@/lib/prisma';
import { ok, badRequest, notFound, conflict, serverError } from '@/lib/http';
import { requireAdminUser } from '@/lib/admin-guard';
import { z } from 'zod';
import { getProductOptionsWithValues, variantTitleFromMap } from '@/lib/product';
import { makeSku } from '@/lib/sku';
import { getDefaultWarehouseId } from '@/lib/warehouse';

export const runtime = 'nodejs';

const comboSchema = z.object({
  values: z.record(z.string(), z.string()), // { Size: "M", Color: "Black" }
  skuSuffix: z.string().max(40).optional(),
  title: z.string().max(200).optional(),
  priceCents: z.number().int().min(0).optional(),
  compareAtCents: z.number().int().min(0).nullable().optional(),
  costCents: z.number().int().min(0).nullable().optional(),
  isDefault: z.boolean().optional(),
  initialStock: z.number().int().min(0).optional(),
});
const bodySchema = z.object({
  currency: z.string().length(3).default('EUR'),
  combinations: z.array(comboSchema).optional(),
  generateAll: z.boolean().optional(),         // if true, create cartesian product from existing options
  priceCents: z.number().int().min(0).optional(), // default price for generateAll
  initialStock: z.number().int().min(0).optional(),
});

export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const variants = await prisma.productVariant.findMany({
    where: { productId: id },
    include: { variantOptions: true, stockLevels: true },
    orderBy: { createdAt: 'asc' },
  });
  return ok(variants);
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

  const opts = await getProductOptionsWithValues(id);
  const nameToOption = new Map(opts.map(o => [o.name, o]));
  const whId = await getDefaultWarehouseId();

  const tasks: any[] = [];

  if (parsed.data.generateAll) {
    if (!parsed.data.priceCents) return badRequest('priceCents is required when generateAll=true');
    // build cartesian product of all option values
    const names = opts.map(o => o.name);
    if (names.length === 0) return badRequest('No options defined to generate from');

    function cartesian(idx: number, acc: Record<string,string>, list: Record<string,string>[]) {
      if (idx === names.length) { list.push({ ...acc }); return; }
      const opt = opts[idx];
      for (const v of opt.values) {
        acc[opt.name] = v.value;
        cartesian(idx + 1, acc, list);
      }
    }
    const combos: Record<string,string>[] = [];
    cartesian(0, {}, combos);

    for (const values of combos) {
      tasks.push({ values, priceCents: parsed.data.priceCents!, initialStock: parsed.data.initialStock ?? 0 });
    }
  } else if (parsed.data.combinations?.length) {
    for (const c of parsed.data.combinations) {
      tasks.push(c);
    }
  } else {
    return badRequest('Provide combinations[] or set generateAll=true');
  }

  try {
    const results = await prisma.$transaction(async (tx) => {
      const created: any[] = [];
      for (const c of tasks) {
        // map values -> option/value ids
        const parts: string[] = [];
        const mapping: { optionId: string; valueId: string }[] = [];
        for (const [name, val] of Object.entries(c.values)) {
          const opt = nameToOption.get(name);
          if (!opt) throw new Error(`Unknown option: ${name}`);
          const v = opt.values.find(x => x.value === val);
          if (!v) throw new Error(`Unknown value for ${name}: ${val}`);
          mapping.push({ optionId: opt.id, valueId: v.id });
          parts.push(String(val));
        }

        const title = c.title ?? variantTitleFromMap(product.title, c.values);
        const sku = makeSku(product.skuPrefix, [parts.join('-')]);

        const v = await tx.productVariant.create({
          data: {
            productId: id,
            sku,
            title,
            currency: parsed.data.currency,
            priceCents: c.priceCents ?? parsed.data.priceCents ?? 0,
            compareAtCents: c.compareAtCents ?? null,
            costCents: c.costCents ?? null,
            isDefault: c.isDefault ?? false,
            variantOptions: { create: mapping },
          },
        });

        if (typeof c.initialStock === 'number') {
          await tx.stockLevel.upsert({
            where: { variantId_warehouseId: { variantId: v.id, warehouseId: whId } },
            update: { onHand: c.initialStock },
            create: { variantId: v.id, warehouseId: whId, onHand: c.initialStock, reserved: 0 },
          });
        }

        created.push(v);
      }
      return created;
    });

    // weak audit per variant create (batch)
    for (const v of results) {
      await prisma.auditLog.create({
        data: { actorUserId: user.id, action: 'variant.create', entityType: 'ProductVariant', entityId: v.id, after: v },
      });
    }

    return ok({ created: results }, { status: 201 });
  } catch (e: any) {
    if (e?.code === 'P2002') return conflict('Duplicate SKU');
    return serverError('Failed to create variants', e);
  }
}
