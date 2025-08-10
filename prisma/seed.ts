/* prisma/seed.ts */
import { PrismaClient } from '@prisma/client';
import bcrypt from 'bcryptjs';

const prisma = new PrismaClient();

async function main() {
  await prisma.config.upsert({
    where: { key: 'currency.default' },
    update: { value: { code: 'EUR' } },
    create: { key: 'currency.default', value: { code: 'EUR' } },
  });

  const adminEmail = 'admin@local.test';
  const adminPass = 'admin123!'; // change later
  const hashed = await bcrypt.hash(adminPass, 12);

  await prisma.user.upsert({
    where: { email: adminEmail },
    update: { role: 'ADMIN', status: 'ACTIVE', hashedPassword: hashed },
    create: {
      email: adminEmail,
      role: 'ADMIN',
      status: 'ACTIVE',
      name: 'Admin',
      hashedPassword: hashed,
    },
  });

  const wh = await prisma.warehouse.upsert({
    where: { code: 'MAIN' },
    update: {},
    create: { code: 'MAIN', name: 'Main Warehouse', isDefault: true },
  });

  const brand = await prisma.brand.upsert({
    where: { slug: 'vexo' },
    update: {},
    create: { name: 'Vexo', slug: 'vexo', description: 'Modern streetwear' },
  });

  const catMen = await prisma.category.upsert({
    where: { slug: 'men' },
    update: {},
    create: { name: 'Men', slug: 'men' },
  });
  const catTees = await prisma.category.upsert({
    where: { slug: 't-shirts' },
    update: {},
    create: { name: 'T-Shirts', slug: 't-shirts', parentId: catMen.id },
  });

  const product = await prisma.product.upsert({
    where: { slug: 'core-logo-tee' },
    update: {},
    create: {
      title: 'Core Logo Tee',
      slug: 'core-logo-tee',
      description: 'Midweight cotton tee with Vexo core logo.',
      status: 'PUBLISHED',
      brandId: brand.id,
      categories: { create: [{ categoryId: catTees.id }] },
      images: {
        create: [
          { url: 'https://picsum.photos/seed/tee1/800/800', alt: 'Core Logo Tee 1', position: 0 },
          { url: 'https://picsum.photos/seed/tee2/800/800', alt: 'Core Logo Tee 2', position: 1 },
        ],
      },
      options: {
        create: [
          { name: 'Size', position: 0, values: { create: [{ value: 'S' }, { value: 'M' }, { value: 'L' }] } },
          { name: 'Color', position: 1, values: { create: [{ value: 'Black' }, { value: 'White' }] } },
        ],
      },
    },
  });

  const sizeOpt = await prisma.productOption.findFirstOrThrow({
    where: { productId: product.id, name: 'Size' },
    include: { values: true },
  });
  const colorOpt = await prisma.productOption.findFirstOrThrow({
    where: { productId: product.id, name: 'Color' },
    include: { values: true },
  });

  const eur = 'EUR';
  const basePrice = 2499;

  for (const s of sizeOpt.values) {
    for (const c of colorOpt.values) {
      const sku = `TEE-CORE-${c.value[0]}-${s.value}`;
      const title = `${product.title} - ${c.value} / ${s.value}`;
      const variant = await prisma.productVariant.upsert({
        where: { sku },
        update: {},
        create: {
          productId: product.id,
          sku,
          title,
          priceCents: basePrice,
          currency: eur,
          trackInventory: true,
          variantOptions: {
            create: [
              { optionId: sizeOpt.id, valueId: s.id },
              { optionId: colorOpt.id, valueId: c.id },
            ],
          },
        },
      });
      await prisma.stockLevel.upsert({
        where: { variantId_warehouseId: { variantId: variant.id, warehouseId: wh.id } },
        update: { onHand: 50, reserved: 0 },
        create: { variantId: variant.id, warehouseId: wh.id, onHand: 50, reserved: 0 },
      });
    }
  }

  console.log('Seed complete. Admin:', adminEmail, 'password:', adminPass);
}

main().catch((e) => { console.error(e); process.exit(1); })
  .finally(async () => { await prisma.$disconnect(); });
