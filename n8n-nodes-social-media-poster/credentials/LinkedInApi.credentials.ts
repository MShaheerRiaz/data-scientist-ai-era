import type { ICredentialType, INodeProperties } from 'n8n-workflow';

export class LinkedInApiCredentials implements ICredentialType {
	name = 'linkedInApiCredentials';
	displayName = 'LinkedIn API';
	documentationUrl =
		'https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow';
	properties: INodeProperties[] = [
		{
			displayName: 'Access Token',
			name: 'accessToken',
			type: 'string',
			typeOptions: { password: true },
			default: '',
			required: true,
			hint: 'OAuth 2.0 Bearer token with w_member_social scope (expires in 60 days)',
		},
		{
			displayName: 'Person URN',
			name: 'personUrn',
			type: 'string',
			default: '',
			required: true,
			hint: 'Your LinkedIn person URN — format: urn:li:person:XXXXXXX (found in LinkedIn developer tools)',
		},
	];
	authenticate = {
		type: 'generic' as const,
		properties: {
			headers: {
				Authorization: '=Bearer {{$credentials.accessToken}}',
			},
		},
	};
	test = {
		request: {
			baseURL: 'https://api.linkedin.com',
			url: '/v2/userinfo',
		},
	};
}
