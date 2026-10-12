import type { INodeProperties } from 'n8n-workflow';

export const blueskyFields: INodeProperties[] = [
	{
		displayName: 'Post Text',
		name: 'text',
		type: 'string',
		typeOptions: { rows: 4 },
		default: '',
		required: true,
		description: 'Text content of the post (max 300 characters)',
		placeholder: 'What\'s on your mind?',
	},
	{
		displayName: 'Additional Options',
		name: 'additionalOptions',
		type: 'collection',
		placeholder: 'Add Option',
		default: {},
		options: [
			{
				displayName: 'Link URL',
				name: 'linkUrl',
				type: 'string',
				default: '',
				description: 'Attach an external link card to the post',
				placeholder: 'https://example.com',
			},
			{
				displayName: 'Link Title',
				name: 'linkTitle',
				type: 'string',
				default: '',
				description: 'Title for the link card',
			},
			{
				displayName: 'Link Description',
				name: 'linkDescription',
				type: 'string',
				default: '',
				description: 'Description for the link card',
			},
		],
	},
];
