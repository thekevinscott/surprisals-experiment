// AWS EC2 Price List, Linux/shared m7i.large in us-east-1, effective 2026-11-01.
export const awsHourlyRate=0.1008
export const awsRateSource='https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/us-east-1/index.csv'
export const awsCostTooltip=`Estimated on-demand compute only; EBS and data transfer excluded. Assumes one Linux m7i.large in us-east-1 at $${awsHourlyRate}/hour, from recorded instance launch to run end (or now). Source: AWS EC2 Price List, effective 2026-11-01: ${awsRateSource}`
export function awsCost(run,now) {
  if(!run.awsLaunched)return null
  const start=Date.parse(run.awsLaunched),end=run.ended ? Date.parse(run.ended) : now
  return Number.isFinite(start)&&Number.isFinite(end) ? Math.max(0,end-start)/3600000*awsHourlyRate : null
}
