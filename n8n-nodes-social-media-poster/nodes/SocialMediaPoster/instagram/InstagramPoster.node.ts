import type {
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
} from 'n8n-workflow';
import { NodeConnectionTypes, NodeOperationError } from 'n8n-workflow';
import { instagramFields } from './PostDescription';

async function pollContainerStatus(
	context: IExecuteFunctions,
	baseUrl: string,
	containerId: string,
	accessToken: string,
	itemIndex: number,
): Promise<void> {
	const maxRetries = 15;
	const delayMs = 3000;

	for (let attempt = 0; attempt < maxRetries; attempt++) {
		await new Promise((resolve) => setTimeout(resolve, delayMs));

		const statusResponse = (await context.helpers.httpRequest({
			method: 'GET',
			url: `${baseUrl}/${containerId}`,
			qs: {
				fields: 'status_code',
				access_token: accessToken,
			},
			json: true,
		})) as { status_code?: string };

		if (statusResponse?.status_code === 'FINISHED') return;
		if (statusResponse?.status_code === 'ERROR') {
			throw new NodeOperationError(
				context.getNode(),
				'Instagram media container processing failed',
				{ itemIndex },
			);
		}
	}

	throw new NodeOperationError(
		context.getNode(),
		'Instagram media container processing timed out after 45 seconds',
		{ itemIndex },
	);
}

export class InstagramPoster implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'Instagram Poster',
		name: 'instagramPoster',
		icon: 'file:instagram.svg',
		group: ['output'],
		version: 1,
		subtitle: 'Post to Instagram Business',
		description: 'Post images, videos, or reels to an Instagram Business account via the Graph API',
		defaults: { name: 'Instagram Poster' },
		usableAsTool: true,
		inputs: [NodeConnectionTypes.Main],
		outputs: [NodeConnectionTypes.Main],
		credentials: [{ name: 'instagramApiCredentials', required: true }],
		properties: instagramFields,
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();
		const returnData: INodeExecutionData[] = [];

		const creds = await this.getCredentials('instagramApiCredentials');
		const igUserId = creds.igUserId as string;
		const accessToken = creds.accessToken as string;
		const apiVersion = (creds.apiVersion as string) || 'v21.0';
		const baseUrl = `https://graph.facebook.com/${apiVersion}`;

		for (let i = 0; i < items.length; i++) {
			try {
				const mediaType = this.getNodeParameter('mediaType', i) as string;
				const mediaUrl = this.getNodeParameter('mediaUrl', i) as string;
				const caption = this.getNodeParameter('caption', i, '') as string;

				if (!mediaUrl.trim()) {
					throw new NodeOperationError(this.getNode(), 'Media URL is required for Instagram posts', {
						itemIndex: i,
					});
				}

				// Step 1: Create the media container
				const containerBody: Record<string, string> = {
					access_token: accessToken,
					media_type: mediaType,
				};

				if (mediaType === 'IMAGE') {
					containerBody.image_url = mediaUrl;
				} else {
					containerBody.video_url = mediaUrl;
				}

				if (caption) {
					containerBody.caption = caption;
				}

				const containerResponse = (await this.helpers.httpRequest({
					method: 'POST',
					url: `${baseUrl}/${igUserId}/media`,
					body: containerBody,
					json: true,
				})) as { id?: string };

				if (!containerResponse?.id) {
					throw new NodeOperationError(
						this.getNode(),
						'Failed to create Instagram media container — no ID returned',
						{ itemIndex: i },
					);
				}

				// For videos/reels, poll until the container is ready
				if (mediaType !== 'IMAGE') {
					await pollContainerStatus(this, baseUrl, containerResponse.id, accessToken, i);
				}

				// Step 2: Publish the container
				const publishResponse = (await this.helpers.httpRequest({
					method: 'POST',
					url: `${baseUrl}/${igUserId}/media_publish`,
					body: {
						creation_id: containerResponse.id,
						access_token: accessToken,
					},
					json: true,
				})) as { id?: string };

				returnData.push({
					json: {
						platform: 'instagram',
						success: true,
						mediaId: publishResponse?.id,
						raw: publishResponse,
					},
					pairedItem: { item: i },
				});
			} catch (error) {
				if (this.continueOnFail()) {
					returnData.push({
						json: { error: (error as Error).message, platform: 'instagram' },
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
