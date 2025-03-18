//
//  NewsView.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 1/7/25.
//

import SwiftUI

struct NewsView: View {
    let news: News
    let relatedNews: [News]
    
    var body: some View {
        GeometryReader { geometry in
            ScrollView {
                VStack {
                    VStack(alignment: .leading, spacing: 16) {
                        Text(news.title)
                            .font(.title)
                            .fontWeight(.bold)
                        
                        AsyncImage(url: URL(string: news.imageUrl ?? "")) { image in
                            image.image?
                                .resizable()
                                .scaledToFit()
                        }
                        .frame(maxWidth: .infinity)
                        .clipShape(.rect(cornerRadius: 16))
                        
                        Text(news.description)
                    }
                    .padding()
                    
                    Spacer()
                    
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack {
                            ForEach(relatedNews) { new in
                                NavigationLink(destination: NewsView(news: new, relatedNews: relatedNews)) {
                                    MediaHeadlineView(news: new)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                        .padding(.leading, 16)
                    }
                }
                .frame(minHeight: geometry.size.height)
            }
            .scrollBounceBehavior(.basedOnSize)
        }
    }
}

#Preview {
    NewsView(news: .mock, relatedNews: [.mock, .mock, .mock])
}
