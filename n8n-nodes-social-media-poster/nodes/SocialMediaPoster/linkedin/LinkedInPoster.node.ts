import type {
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
} from 'n8n-workflow';
import { NodeConnectionTypes } from 'n8n-workflow';
import { linkedInFields } from './PostDescription';

export class LinkedInPoster implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'LinkedIn Poster',
		name: 'linkedInPoster',
		icon: 'file:linkedin.svg',
		group: ['output'],
		version: 1,
		subtitle: 'Post to LinkedIn',
		description: 'Share text or article posts on LinkedIn via the UGC Posts API',
		defaults: { name: 'LinkedIn Poster' },
		usableAsTool: true,
		inputs: [NodeConnectionTypes.Main],
		outputs: [NodeConnectionTypes.Main],
		credentials: [{ name: 'linkedInApiCredentials', required: true }],
		properties: linkedInFields,
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();
		const returnData: INodeExecutionData[] = [];

		const creds = await this.getCredentials('linkedInApiCredentials');
		const accessToken = creds.accessToken as string;
		const personUrn = creds.personUrn as string;

		for (let i = 0; i < items.length; i++) {
			try {
				const postType = this.getNodeParameter('postType', i) as string;
				const message = this.getNodeParameter('message', i) as string;

				// eslint-disable-next-line @typescript-eslint/no-explicit-any
				const shareContent: Record<string, any> = {
					shareCommentary: { text: message },
					shareMediaCategory: postType,
				};

				if (postType === 'ARTICLE') {
					const articleUrl = this.getNodeParameter('articleUrl', i) as string;
					const articleTitle = this.getNodeParameter('articleTitle', i, '') as string;
					const articleDescription = this.getNodeParameter('articleDescription', i, '') as string;

					shareContent.media = [
						{
							status: 'READY',
							originalUrl: articleUrl,
							title: { text: articleTitle },
							description: { text: articleDescription },
						},
					];
				}

				const body = {
					author: personUrn,
					lifecycleState: 'PUBLISHED',
					specificContent: {
						'com.linkedin.ugc.ShareContent': shareContent,
					},
					visibility: {
						'com.linkedin.ugc.MemberNetworkVisibility': 'PUBLIC',
					},
				};

				const response = (await this.helpers.httpRequest({
					method: 'POST',
					url: 'https://api.linkedin.com/v2/ugcPosts',
					headers: {
						Authorization: `Bearer ${accessToken}`,
						'Content-Type': 'application/json',
						'X-Restli-Protocol-Version': '2.0.0',
					},
					body,
					json: true,
				})) as { id?: string };

				returnData.push({
					json: { platform: 'linkedin', success: true, postId: response?.id, raw: response },
					pairedItem: { item: i },
				});
			} catch (error) {
				if (this.continueOnFail()) {
					returnData.push({
						json: { error: (error as Error).message, platform: 'linkedin' },
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
