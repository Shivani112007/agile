#!/bin/bash
# Creates the 3 DynamoDB tables (run once with AWS CLI configured)
for t in students opportunities applications; do
  aws dynamodb create-table --table-name SkillPortal-$t --attribute-definitions AttributeName=id,AttributeType=S \
    --key-schema AttributeName=id,KeyType=HASH --billing-mode PAY_PER_REQUEST --region ap-south-1
done
