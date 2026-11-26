import { test, expect } from '@playwright/test';

test('player portal shows the registered Minecraft server', async ({ page }) => {
  await page.route('**/api/v1/public/servers/terra-smp', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      id: 'server-1',
      name: 'Terra SMP',
      slug: 'terra-smp',
      description: 'Sobrevivência com a comunidade.',
      status: 'active',
      image_url: null,
    }),
  }));
  await page.route('**/api/v1/pairing/status', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ paired: false }),
  }));

  await page.goto('/?tenant=terra-smp');
  await expect(page.getByRole('heading', { name: 'Terra SMP' })).toBeVisible();
  await expect(page.getByText('Sobrevivência com a comunidade.')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Entrar na voz' })).toBeVisible();
});

test('owner can register a server with a cover image', async ({ page }) => {
  let coverUploaded = false;
  await page.route('**/api/v1/auth/login', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ access_token: 'playwright-owner-token' }),
  }));
  await page.route('**/api/v1/dashboard/servers', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      servers: coverUploaded ? [{
        id: 'server-1',
        name: 'Terra SMP',
        slug: 'terra-smp',
        status: 'pending',
        subdomain: 'https://terra-smp.voice-horizon.online',
        description: 'Meu mundo Bedrock',
        image_url: '/api/v1/public/servers/terra-smp/image',
      }] : [],
    }),
  }));
  await page.route('**/api/v1/servers', route => route.fulfill({
    status: 201,
    contentType: 'application/json',
    body: JSON.stringify({
      server_id: 'server-1',
      activation_code: 'HV-TEST-CODE',
      subdomain: 'https://terra-smp.voice-horizon.online',
    }),
  }));
  await page.route('**/api/v1/dashboard/servers/server-1/image', async route => {
    const contentType = route.request().headers()['content-type'] || '';
    expect(contentType).toContain('image/webp');
    coverUploaded = true;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ uploaded: true, image_url: '/api/v1/public/servers/terra-smp/image' }),
    });
  });

  await page.goto('/');
  await page.getByRole('button', { name: /Painel do servidor/ }).click();
  await page.getByLabel('E-mail').fill('owner@example.com');
  await page.getByLabel('Senha').fill('CorrectHorseBattery!2026');
  await page.getByRole('button', { name: /^Entrar/ }).click();

  await page.getByLabel('Nome do servidor').fill('Terra SMP');
  await page.getByLabel('Endereço do portal').locator('input').fill('terra-smp');
  await page.getByLabel('Descrição do servidor').fill('Meu mundo Bedrock');
  await page.locator('#server-image').setInputFiles({
    name: 'cover.png',
    mimeType: 'image/png',
    buffer: Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/N5sAAAAASUVORK5CYII=',
      'base64',
    ),
  });

  await page.getByRole('button', { name: /Criar servidor/ }).click();
  await expect(page.getByText('Terra SMP').last()).toBeVisible();
  await expect(page.getByText('Abrir portal')).toBeVisible();
  expect(coverUploaded).toBe(true);
});
