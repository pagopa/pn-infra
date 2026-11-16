'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { selectPartition } = require('../../lib/partition');

const scheduled = time => ({
  mode: 'scheduled',
  scheduleArn: 'arn:aws:scheduler:eu-south-1:123456789012:schedule/default/pn-downstream-compaction',
  scheduledTime: time,
});

test('scheduled partitions use the event time even when delivery is delayed', () => {
  const result = selectPartition(scheduled('2026-11-04T10:05:00Z'), new Date('2026-11-04T15:00:00Z'), 120);
  assert.equal(result.hour, '2026-11-04T10');
  assert.equal(result.path, '2026/11/04/10');
  assert.deepEqual(result.values, ['2026', '11', '04', '10']);
});

test('handles midnight, month and year boundaries', () => {
  const result = selectPartition(scheduled('2027-01-01T00:05:00Z'), new Date('2027-01-01T00:06:00Z'), 120);
  assert.equal(result.hour, '2027-01-01T00');
  const previous = selectPartition(scheduled('2026-12-31T23:05:00Z'), new Date('2026-12-31T23:06:00Z'), 120);
  assert.equal(previous.hour, '2026-12-31T23');
});

test('does not publish the repeated autumn hour before both occurrences have closed', () => {
  assert.equal(selectPartition(scheduled('2026-10-25T01:05:00Z'), new Date('2026-10-25T01:06:00Z'), 120), null);
  assert.equal(selectPartition(scheduled('2026-10-25T02:05:00Z'), new Date('2026-10-25T02:06:00Z'), 120).hour,
    '2026-10-25T02');
  assert.throws(() => selectPartition({ mode: 'manual', partitionHour: '2026-10-25T02' },
    new Date('2026-10-25T01:05:00Z'), 120), /still open/);
});

test('skips the nonexistent spring hour', () => {
  assert.equal(selectPartition(scheduled('2026-03-29T01:05:00Z'), new Date('2026-03-29T01:06:00Z'), 120).hour,
    '2026-03-29T01');
  assert.throws(() => selectPartition({ mode: 'manual', partitionHour: '2026-03-29T02' },
    new Date('2026-03-29T05:00:00Z'), 120), /does not exist/);
});

test('requires a valid explicit closed hour for manual invocations', () => {
  const now = new Date('2026-11-04T10:05:00Z');
  assert.equal(selectPartition({ mode: 'manual', partitionHour: '2026-11-04T10' }, now, 120).hour, '2026-11-04T10');
  for (const partitionHour of [undefined, '2026-02-30T10', '2026-11-04T24', '2026-11-04T11', '2026-11-04T10Z']) {
    assert.throws(() => selectPartition({ mode: 'manual', partitionHour }, now, 120));
  }
  assert.throws(() => selectPartition({}, now, 120), /explicit partitionHour/);
  assert.throws(() => selectPartition(scheduled('2026-11-04T10:00:30Z'), now, 120), /settling/);
});
