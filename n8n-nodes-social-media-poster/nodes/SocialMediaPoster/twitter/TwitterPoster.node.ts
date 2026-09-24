import crypto from 'crypto';
import type {
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
} from 'n8n-workflow';
import { NodeConnectionTypes, NodeOperationError } from 'n8n-workflow';
import OAuth from 'oauth-1.0a';
import { twitterFields } from './PostDescription';

export class TwitterPoster implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'Twitter / X Poster',
		name: 'twitterPoster',
		icon: 'file:twitter.svg',
		group: ['output'],
		version: 1,
		subtitle: 'Post a tweet',
		description: 'Post tweets to Twitter/X using the v2 API',
		defaults: { name: 'Twitter / X Poster' },
		usableAsTool: true,
		inputs: [NodeConnectionTypes.Main],
		outputs: [NodeConnectionTypes.Main],
		credentials: [{ name: 'twitterApi', required: true }],
		properties: twitterFields,
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();
		const returnData: INodeExecutionData[] = [];

		const creds = await this.getCredentials('twitterApi');

		const oauth = new OAuth({
			consumer: {
				key: creds.apiKey as string,
				secret: creds.apiSecret as string,
			},
			signature_method: 'HMAC-SHA1',
			hash_function(baseString, key) {
				return crypto.createHmac('sha1', key).update(baseString).digest('base64');
			},
		});

		for (let i = 0; i < items.length; i++) {
			try {
				const text = this.getNodeParameter('text', i) as string;
				if (!text.trim()) {
					throw new NodeOperationError(this.getNode(), 'Tweet text cannot be empty', {
						itemIndex: i,
					});
				}

				const additionalOptions = this.getNodeParameter('additionalOptions', i, {}) as {
					replyToTweetId?: string;
				};

				const body: Record<string, unknown> = { text };
				if (additionalOptions.replyToTweetId) {
					body.reply = { in_reply_to_tweet_id: additionalOptions.replyToTweetId };
				}

				const url = 'https://api.twitter.com/2/tweets';
				const token = {
					key: creds.accessToken as string,
					secret: creds.accessTokenSecret as string,
				};

				const authHeader = oauth.toHeader(oauth.authorize({ url, method: 'POST' }, token));

				const response = (await this.helpers.httpRequest({
					method: 'POST',
					url,
					headers: {
						...authHeader,
						'Content-Type': 'application/json',
					},
					body,
					json: true,
				})) as { data?: { id?: string; text?: string } };

				returnData.push({
					json: {
						platform: 'twitter',
						success: true,
						tweetId: response?.data?.id,
						text: response?.data?.text,
						raw: response,
					},
					pairedItem: { item: i },
				});
			} catch (error) {
				if (this.continueOnFail()) {
					returnData.push({
						json: { error: (error as Error).message, platform: 'twitter' },
						pairedItem: { item: i },
					});
					continue;
				}
				throw error;
			}
		}

		return [returnData];
	}
}
