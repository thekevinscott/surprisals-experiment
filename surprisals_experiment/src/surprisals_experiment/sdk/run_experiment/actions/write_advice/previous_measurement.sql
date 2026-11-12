SELECT score AS length, score_text
FROM advices JOIN turn_advice ON turn_advice.advice_id = advices.id
WHERE turn_advice.turn_id = :turn_id
