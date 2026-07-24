import type { ICredentialType, INodeProperties } from 'n8n-workflow';

export class ThreadsApiCredentials implements ICredentialType {
	name = 'threadsApiCredentials';
	displayName = 'Threads API';
	documentationUrl = 'https://developers.facebook.com/docs/threads';
	properties: INodeProperties[] = [
		{
			displayName: 'Threads User ID',
			name: 'userId',
			type: 'string',
			default: '',
			required: true,
			hint: 'Your Threads numeric User ID — retrieve via GET /me?fields=id with your access token',
		},
		{
			displayName: 'Access Token',
			name: 'accessToken',
			type: 'string',
			typeOptions: { password: true },
			default: '',
			required: true,
			hint: 'Threads User Access Token from Meta App Dashboard',
		},
		{
			displayName: 'API Version',
			name: 'apiVersion',
			type: 'string',
			default: 'v21.0',
		},
	];
}
