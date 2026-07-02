import type { ICredentialType, INodeProperties } from 'n8n-workflow';

export class InstagramApiCredentials implements ICredentialType {
	name = 'instagramApiCredentials';
	displayName = 'Instagram Graph API';
	documentationUrl = 'https://developers.facebook.com/docs/instagram-api';
	properties: INodeProperties[] = [
		{
			displayName: 'Instagram Business User ID',
			name: 'igUserId',
			type: 'string',
			default: '',
			required: true,
			hint: 'Your Instagram Business Account numeric User ID (found in Meta Business Suite or via GET /me)',
		},
		{
			displayName: 'Page Access Token',
			name: 'accessToken',
			type: 'string',
			typeOptions: { password: true },
			default: '',
			required: true,
			hint: 'Page Access Token from the Facebook Page connected to your Instagram Business account',
		},
		{
			displayName: 'API Version',
			name: 'apiVersion',
			type: 'string',
			default: 'v21.0',
		},
	];
}
