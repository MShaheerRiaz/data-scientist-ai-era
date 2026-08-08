import type {
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
} from 'n8n-workflow';
import { NodeConnectionTypes } from 'n8n-workflow';
import { blueskyFields } from './PostDescription';

interface BlueskySession {
	accessJwt: string;
	did: string;
}

export class BlueskyPoster implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'Bluesky Poster',
		name: 'blueskyPoster',
		icon: 'file:bluesky.svg',
		group: ['output'],
		version: 1,
		subtitle: 'Post to Bluesky',
		description: 'Post to Bluesky via the AT Protocol',
		defaults: { name: 'Bluesky Poster' },
		usableAsTool: true,
		inputs: [NodeConnectionTypes.Main],
		outputs: [NodeConnectionTypes.Main],
		credentials: [{ name: 'blueskyApiCredentials', required: true }],
		properties: blueskyFields,
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();
		const returnData: INodeExecutionData[] = [];

		const creds = await this.getCredentials('blueskyApiCredentials');
		const serviceUrl = (creds.serviceUrl as string) || 'https://bsky.social';

		for (let i = 0; i < items.length; i++) {
			try {
				// Authenticate and get a fresh session token
				const session = (await this.helpers.httpRequest({
					method: 'POST',
					url: `${serviceUrl}/xrpc/com.atproto.server.createSession`,
					body: {
						identifier: creds.identifier as string,
						password: creds.password as string,
					},
					json: true,
				})) as BlueskySession;

				const text = this.getNodeParameter('text', i) as string;
				const additionalOptions = this.getNodeParameter('additionalOptions', i, {}) as {
					linkUrl?: string;
					linkTitle?: string;
					linkDescription?: string;
				};

				// eslint-disable-next-line @typescript-eslint/no-explicit-any
				const record: Record<string, any> = {
					$type: 'app.bsky.feed.post',
					text,
					createdAt: new Date().toISOString(),
				};

				if (additionalOptions.linkUrl) {
					record.embed = {
						$type: 'app.bsky.embed.external',
						external: {
							uri: additionalOptions.linkUrl,
							title: additionalOptions.linkTitle || '',
							description: additionalOptions.linkDescription || '',
						},
					};
				}

				const response = (await this.helpers.httpRequest({
					method: 'POST',
					url: `${serviceUrl}/xrpc/com.atproto.repo.createRecord`,
					headers: {
						Authorization: `Bearer ${session.accessJwt}`,
						'Content-Type': 'application/json',
					},
					body: {
						repo: session.did,
						collection: 'app.bsky.feed.post',
						record,
					},
					json: true,
				})) as { uri?: string; cid?: string };

				returnData.push({
					json: {
						platform: 'bluesky',
						success: true,
						uri: response?.uri,
						cid: response?.cid,
						raw: response,
					},
					pairedItem: { item: i },
				});
			} catch (error) {
				if (this.continueOnFail()) {
					returnData.push({
						json: { error: (error as Error).message, platform: 'bluesky' },
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
