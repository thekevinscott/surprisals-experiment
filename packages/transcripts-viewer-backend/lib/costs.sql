WITH priced AS MATERIALIZED (
 SELECT *,max(0,(coalesce(unixepoch(ended,'subsec'),:now/1000.0)-unixepoch(awsLaunched,'subsec')))/3600*0.1008 AS awsCost FROM cost_rows
), totals AS (
 SELECT coalesce(sum(uCost),0) AS u,coalesce(sum(tCost),0) AS t,coalesce(sum(awsCost),0) AS aws,
 count(*)-count(uCost) AS missing_u,count(*)-count(tCost) AS missing_t,count(*)-count(awsCost) AS missing_aws FROM priced
), pod_total AS (
 SELECT coalesce(sum(max(0,coalesce(unixepoch(stop,'subsec'),:now/1000.0)-unixepoch(start,'subsec'))/3600*costPerHr),0) AS runpod FROM pod_records
) SELECT json_object('asOf',:now,
 'rows',json((SELECT json_group_array(json_object('id',id,'uCost',uCost,'tCost',tCost,'modelCost',uCost+tCost,'awsLaunched',awsLaunched,'ended',ended,'awsCost',awsCost)) FROM (SELECT * FROM priced ORDER BY id))),
 'pods',json((SELECT json_group_array(json_object('id',id,'gpu',gpu,'costPerHr',costPerHr,'start',start,'stop',stop)) FROM (SELECT * FROM pod_records ORDER BY path))),
 'breakdown',json_object('u',u,'t',t,'aws',aws,'runpod',runpod,'total',u+t+aws+runpod,'missing',json_object('u',missing_u,'t',missing_t,'aws',missing_aws)),
 'warnings',json(CASE WHEN EXISTS(SELECT 1 FROM transcript_lines WHERE incomplete) THEN '["Incomplete usage records were skipped; costs may be partial."]' ELSE '[]' END)
) AS payload FROM totals CROSS JOIN pod_total;
