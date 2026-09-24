import type { IExecuteFunctions, IHttpRequestOptions } from 'n8n-workflow';
import { NodeApiError, NodeOperationError } from 'n8n-workflow';

export async function socialMediaRequest(
	context: IExecuteFunctions,
	options: IHttpRequestOptions,
	itemIndex = 0,
): Promise<unknown> {
	try {
		return await context.helpers.httpRequest(options);
	} catch (error: unknown) {
		if (error && typeof error === 'object' && 'response' in error) {
			throw new NodeApiError(context.getNode(), error as unknown as { message: string }, {
				itemIndex,
			});
		}
		throw new NodeOperationError(
			context.getNode(),
			error instanceof Error ? error.message : 'Unknown error occurred',
			{ itemIndex },
		);
	}
}
