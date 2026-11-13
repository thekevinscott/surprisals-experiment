import test from 'node:test'
import assert from 'node:assert/strict'
import {awsCost,awsHourlyRate,awsCostTooltip} from '../src/composables/awsCost.js'
test('AWS estimate uses launch instead of run start, advances live, and stops at run end',()=>{
 const row={awsLaunched:'2026-11-13T01:00:00Z',started:'2026-11-13T00:00:00Z'}
 const now=Date.parse('2026-11-13T03:00:00Z')
 assert.equal(awsCost(row,now),2*awsHourlyRate)
 assert.equal(awsCost(row,now+3600000),3*awsHourlyRate)
 assert.equal(awsCost({...row,ended:'2026-11-13T02:00:00Z'},now),awsHourlyRate)
 assert.equal(awsCost({},now),null)
 assert.equal(awsCost({...row,awsLaunched:'invalid'},now),null)
 assert.equal(awsCost(row,0),0)
 assert.match(awsCostTooltip,/EBS and data transfer excluded/)
 assert.match(awsCostTooltip,/0.1008/)
 assert.match(awsCostTooltip,/https:\/\/pricing.us-east-1.amazonaws.com/)
})
