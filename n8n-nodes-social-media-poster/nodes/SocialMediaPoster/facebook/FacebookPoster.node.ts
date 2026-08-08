import type {
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
} from 'n8n-workflow';
import { NodeConnectionTypes } from 'n8n-workflow';
import { facebookFields } from './PostDescription';

export class FacebookPoster implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'Facebook Page Poster',
		name: 'facebookPoster',
		icon: 'file:facebook.svg',
		group: ['output'],
		version: 1,
		subtitle: 'Post to a Facebook Page',
		description: 'Post text, photos, or links to a Facebook Page via the Graph API',
		defaults: { name: 'Facebook Page Poster' },
		usableAsTool: true,
		inputs: [NodeConnectionTypes.Main],
		outputs: [NodeConnectionTypes.Main],
		credentials: [{ name: 'facebookGraphApiCredentials', required: true }],
		properties: facebookFields,
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();
		const returnData: INodeExecutionData[] = [];

		const creds = await this.getCredentials('facebookGraphApiCredentials');
		const apiVersion = (creds.apiVersion as string) || 'v21.0';
		const baseUrl = `https://graph.facebook.com/${apiVersion}`;

		for (let i = 0; i < items.length; i++) {
			try {
				const pageId = this.getNodeParameter('pageId', i) as string;
				const postType = this.getNodeParameter('postType', i) as string;
				const message = this.getNodeParameter('message', i) as string;

				let endpoint: string;
				const body: Record<string, string> = {
					message,
					access_token: creds.accessToken as string,
				};

				if (postType === 'photo') {
					endpoint = `${baseUrl}/${pageId}/photos`;
					body.url = this.getNodeParameter('photoUrl', i) as string;
				} else if (postType === 'link') {
					endpoint = `${baseUrl}/${pageId}/feed`;
					body.link = this.getNodeParameter('linkUrl', i) as string;
				} else {
					endpoint = `${baseUrl}/${pageId}/feed`;
				}

				const response = (await this.helpers.httpRequest({
					method: 'POST',
					url: endpoint,
					body,
					json: true,
				})) as { id?: string };

				returnData.push({
					json: { platform: 'facebook', success: true, postId: response?.id, raw: response },
					pairedItem: { item: i },
				});
			} catch (error) {
				if (this.continueOnFail()) {
					returnData.push({
						json: { error: (error as Error).message, platform: 'facebook' },
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
