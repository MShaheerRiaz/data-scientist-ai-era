import type {
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
} from 'n8n-workflow';
import { NodeConnectionTypes, NodeOperationError } from 'n8n-workflow';
import { threadsFields } from './PostDescription';

export class ThreadsPoster implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'Threads Poster',
		name: 'threadsPoster',
		icon: 'file:threads.svg',
		group: ['output'],
		version: 1,
		subtitle: 'Post to Threads',
		description: 'Post text, images, or videos to Threads via the Meta Threads API',
		defaults: { name: 'Threads Poster' },
		usableAsTool: true,
		inputs: [NodeConnectionTypes.Main],
		outputs: [NodeConnectionTypes.Main],
		credentials: [{ name: 'threadsApiCredentials', required: true }],
		properties: threadsFields,
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();
		const returnData: INodeExecutionData[] = [];

		const creds = await this.getCredentials('threadsApiCredentials');
		const userId = creds.userId as string;
		const accessToken = creds.accessToken as string;
		const apiVersion = (creds.apiVersion as string) || 'v21.0';
		const baseUrl = `https://graph.threads.net/${apiVersion}`;

		for (let i = 0; i < items.length; i++) {
			try {
				const mediaType = this.getNodeParameter('mediaType', i) as string;
				const text = this.getNodeParameter('text', i, '') as string;

				const containerBody: Record<string, string> = {
					media_type: mediaType,
					access_token: accessToken,
				};

				if (text) containerBody.text = text;

				if (mediaType === 'IMAGE' || mediaType === 'VIDEO') {
					const mediaUrl = this.getNodeParameter('mediaUrl', i) as string;
					if (!mediaUrl.trim()) {
						throw new NodeOperationError(
							this.getNode(),
							`Media URL is required for ${mediaType} posts`,
							{ itemIndex: i },
						);
					}
					if (mediaType === 'IMAGE') {
						containerBody.image_url = mediaUrl;
					} else {
						containerBody.video_url = mediaUrl;
					}
				}

				// Step 1: Create the media container
				const containerResponse = (await this.helpers.httpRequest({
					method: 'POST',
					url: `${baseUrl}/${userId}/threads`,
					body: containerBody,
					json: true,
				})) as { id?: string };

				if (!containerResponse?.id) {
					throw new NodeOperationError(
						this.getNode(),
						'Failed to create Threads media container — no ID returned',
						{ itemIndex: i },
					);
				}

				// Step 2: Publish
				const publishResponse = (await this.helpers.httpRequest({
					method: 'POST',
					url: `${baseUrl}/${userId}/threads_publish`,
					body: {
						creation_id: containerResponse.id,
						access_token: accessToken,
					},
					json: true,
				})) as { id?: string };

				returnData.push({
					json: {
						platform: 'threads',
						success: true,
						postId: publishResponse?.id,
						raw: publishResponse,
					},
					pairedItem: { item: i },
				});
			} catch (error) {
				if (this.continueOnFail()) {
					returnData.push({
						json: { error: (error as Error).message, platform: 'threads' },
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
