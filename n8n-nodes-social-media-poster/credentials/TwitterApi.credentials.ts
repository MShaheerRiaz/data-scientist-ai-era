import type { ICredentialType, INodeProperties } from 'n8n-workflow';

export class TwitterApi implements ICredentialType {
	name = 'twitterApi';
	displayName = 'Twitter / X API (OAuth 1.0a)';
	documentationUrl = 'https://developer.twitter.com/en/docs/authentication/oauth-1-0a';
	properties: INodeProperties[] = [
		{
			displayName: 'API Key (Consumer Key)',
			name: 'apiKey',
			type: 'string',
			typeOptions: { password: true },
			default: '',
			required: true,
		},
		{
			displayName: 'API Secret (Consumer Secret)',
			name: 'apiSecret',
			type: 'string',
			typeOptions: { password: true },
			default: '',
			required: true,
		},
		{
			displayName: 'Access Token',
			name: 'accessToken',
			type: 'string',
			typeOptions: { password: true },
			default: '',
			required: true,
		},
		{
			displayName: 'Access Token Secret',
			name: 'accessTokenSecret',
			type: 'string',
			typeOptions: { password: true },
			default: '',
			required: true,
			hint: 'All four values are found at developer.twitter.com → Your App → Keys and Tokens',
		},
	];
}
