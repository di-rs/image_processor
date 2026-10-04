process.env.HOST ??= '127.0.0.1';
process.env.BODY_SIZE_LIMIT ??= '50M';

await import('../build/index.js');
