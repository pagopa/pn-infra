'use strict';

const formatter = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Europe/Rome',
  year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', hourCycle: 'h23',
});

function localHour(date) {
  const parts = Object.fromEntries(formatter.formatToParts(date).map(part => [part.type, part.value]));
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}`;
}

function selectPartition(event, now, settleSeconds) {
  let hour;
  let reference;
  if (event.mode === 'manual') {
    hour = event.partitionHour;
    reference = now;
  } else if (event.mode === 'scheduled' && typeof event.scheduleArn === 'string'
      && event.scheduleArn && typeof event.scheduledTime === 'string') {
    reference = new Date(event.scheduledTime);
    if (!Number.isFinite(reference.getTime()) || reference > now) {
      throw new Error('Invalid scheduled event time');
    }
    hour = localHour(new Date(reference.getTime() - 3600000));
    if (hour === localHour(reference)) {
      return null; // Both occurrences of the autumn DST hour share the same source partition.
    }
  } else {
    throw new Error('Expected a scheduled event or manual mode with an explicit partitionHour');
  }

  if (typeof hour !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}$/.test(hour)) {
    throw new Error('partitionHour must be YYYY-MM-DDTHH in Europe/Rome');
  }
  const nominal = new Date(`${hour}:00:00Z`);
  if (!Number.isFinite(nominal.getTime()) || nominal.toISOString().slice(0, 13) !== hour
      || nominal.getUTCFullYear() < 2024 || nominal.getUTCFullYear() > 2099) {
    throw new Error('partitionHour is not a valid date and hour');
  }

  // Find all UTC occurrences, including the repeated autumn hour, without trusting the host timezone.
  const occurrences = [1, 2].map(offset => new Date(nominal.getTime() - offset * 3600000))
    .filter(date => localHour(date) === hour);
  if (occurrences.length === 0) {
    throw new Error('partitionHour does not exist in Europe/Rome');
  }
  const closeTime = Math.max(...occurrences.map(date => date.getTime())) + 3600000;
  if (reference.getTime() < closeTime + settleSeconds * 1000
      || now.getTime() < closeTime + settleSeconds * 1000) {
    throw new Error('The requested partition is still open or its upload settling period has not elapsed');
  }
  return {
    hour,
    path: hour.replace(/[-T]/g, '/'),
    values: [hour.slice(0, 4), hour.slice(5, 7), hour.slice(8, 10), hour.slice(11, 13)],
  };
}

module.exports = { localHour, selectPartition };
