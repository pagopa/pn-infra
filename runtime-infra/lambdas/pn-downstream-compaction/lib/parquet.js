'use strict';

const { ParquetReader, ParquetSchema, ParquetWriter } = require('@dsnp/parquetjs');

const COLUMNS = {
  eventType: 'UTF8',
  timestamp: 'UTF8',
  clientName: 'UTF8',
  method: 'UTF8',
  url: 'UTF8',
  host: 'UTF8',
  status: 'INT32',
  success: 'BOOLEAN',
  outcome: 'UTF8',
  durationMs: 'INT64',
  errorType: 'UTF8',
  errorMessage: 'UTF8',
};

const SCHEMA = new ParquetSchema(Object.fromEntries(
  Object.entries(COLUMNS).map(([name, type]) => [
    name, { type, optional: true, compression: 'SNAPPY' },
  ]),
));

async function appendFile(writer, path, checkDeadline) {
  const reader = await ParquetReader.openFile(path);
  try {
    const fields = reader.schema.fieldList;
    const mapping = Object.keys(COLUMNS).map(name => {
      const field = fields.find(candidate => candidate.name.toLowerCase() === name.toLowerCase());
      const expected = COLUMNS[name] === 'UTF8' ? 'BYTE_ARRAY' : COLUMNS[name];
      if (!field || field.primitiveType !== expected || field.repetitionType === 'REPEATED'
          || (COLUMNS[name] === 'UTF8' && field.originalType !== 'UTF8')) {
        throw new Error(`Unexpected Parquet schema for column ${name}`);
      }
      return [name, field.name];
    });
    if (fields.length !== mapping.length) {
      throw new Error('Unexpected columns in downstream Parquet');
    }

    let rows = 0;
    const cursor = reader.getCursor();
    for (let record = await cursor.next(); record !== null; record = await cursor.next()) {
      checkDeadline();
      await writer.appendRow(Object.fromEntries(mapping.map(([name, source]) => [name, record[source]])));
      rows += 1;
    }
    if (BigInt(rows) !== BigInt(reader.getRowCount())) {
      throw new Error(`Incomplete Parquet input: expected ${reader.getRowCount()}, read ${rows}`);
    }
    return rows;
  } finally {
    await reader.close();
  }
}

async function consolidate(paths, outputPath, checkDeadline = () => {}) {
  const writer = await ParquetWriter.openFile(SCHEMA, outputPath, { rowGroupSize: 1024 });
  let rows = 0;
  try {
    for await (const path of paths) {
      checkDeadline();
      rows += await appendFile(writer, path, checkDeadline);
    }
  } finally {
    await writer.close();
  }

  const reader = await ParquetReader.openFile(outputPath);
  try {
    if (BigInt(reader.getRowCount()) !== BigInt(rows)) {
      throw new Error('Consolidated Parquet row count does not match its inputs');
    }
  } finally {
    await reader.close();
  }
  return rows;
}

module.exports = { COLUMNS, SCHEMA, consolidate };
